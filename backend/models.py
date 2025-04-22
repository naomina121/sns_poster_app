import os
import json
import datetime
import logging
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# ロガーの設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ScheduledPostDB")

# .envファイルから環境変数を読み込む
load_dotenv()

# データベース接続情報を取得
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/sns_poster")
logger.info(f"データベース接続URL: {DATABASE_URL}")

# SQLAlchemyの設定
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
Base = declarative_base()
Session = sessionmaker(bind=engine)

# スケジュール済みの投稿モデル
class ScheduledPost(Base):
    __tablename__ = 'scheduled_posts'

    id = Column(Integer, primary_key=True)
    content = Column(Text, nullable=False)
    platforms = Column(Text, nullable=False)
    scheduled_time = Column(String, nullable=False)
    status = Column(String, default='pending')
    created_at = Column(String, nullable=False)
    media_paths = Column(Text, nullable=True)
    post_mode = Column(String, default='unified')

def ensure_utc(dt):
    """日時をUTCに変換する"""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(datetime.timezone.utc)

def jst_to_utc(jst_dt):
    """JSTの日時をUTCに変換する"""
    jst = datetime.timezone(datetime.timedelta(hours=9))
    if jst_dt.tzinfo is None:
        jst_dt = jst_dt.replace(tzinfo=jst)
    return jst_dt.astimezone(datetime.timezone.utc)

def utc_to_jst(utc_dt):
    """UTCの日時をJSTに変換する"""
    jst = datetime.timezone(datetime.timedelta(hours=9))
    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=datetime.timezone.utc)
    return utc_dt.astimezone(jst)

# データベースのテーブル作成
def create_tables():
    try:
        Base.metadata.create_all(engine)
        logger.info("データベーステーブルを作成しました")
    except Exception as e:
        logger.error(f"テーブル作成エラー: {e}")
        raise

class ScheduledPostDB:
    def __init__(self):
        logger.info(f"データベース接続URL: {DATABASE_URL}")
        self.session = Session()

    def add_scheduled_post(self, content, platforms, scheduled_time, media_paths=None, post_mode='unified'):
        try:
            # 現在時刻をUTCで取得
            now = ensure_utc(datetime.datetime.now()).isoformat()

            # 予約時間のフォーマットを標準化
            try:
                # 入力された時間をJSTとして解釈
                jst = datetime.timezone(datetime.timedelta(hours=9))
                scheduled_dt = datetime.datetime.fromisoformat(scheduled_time.replace('Z', '+09:00'))
                if scheduled_dt.tzinfo is None:
                    scheduled_dt = scheduled_dt.replace(tzinfo=jst)

                # JSTからUTCに変換
                scheduled_dt_utc = scheduled_dt.astimezone(datetime.timezone.utc)
                scheduled_time_iso = scheduled_dt_utc.isoformat()

                logger.info(f"予約時間を標準化: JST={scheduled_dt.isoformat()}, UTC={scheduled_time_iso}")
            except (ValueError, TypeError) as e:
                logger.error(f"予約時間の変換に失敗しました: {e}")
                scheduled_time_iso = scheduled_time

            # オブジェクトをJSON文字列に変換
            if isinstance(content, (dict, list)):
                content = json.dumps(content, ensure_ascii=False)
            if isinstance(platforms, (dict, list)):
                platforms = json.dumps(platforms, ensure_ascii=False)
            if isinstance(media_paths, (dict, list)):
                media_paths = json.dumps(media_paths, ensure_ascii=False)

            new_post = ScheduledPost(
                content=content,
                platforms=platforms,
                scheduled_time=scheduled_time_iso,
                created_at=now,
                media_paths=media_paths,
                post_mode=post_mode
            )

            self.session.add(new_post)
            self.session.commit()

            post_id = new_post.id
            logger.info(f"新規予約投稿を作成しました: ID={post_id}")
            return post_id
        except Exception as e:
            self.session.rollback()
            logger.error(f"予約投稿の作成エラー: {e}")
            raise

    def get_pending_posts(self):
        try:
            # 現在時刻をUTCで取得
            now = ensure_utc(datetime.datetime.now())
            now_iso = now.isoformat()
            logger.info(f"現在時刻（データベース検索用）: {now_iso}")

            # ステータスが'pending'の投稿を全て取得
            posts = self.session.query(ScheduledPost).filter(
                ScheduledPost.status == 'pending'
            ).all()

            # 辞書形式に変換
            result_posts = []
            for post in posts:
                try:
                    # 予約時間の文字列を処理
                    scheduled_time_str = post.scheduled_time
                    if 'Z' in scheduled_time_str:
                        scheduled_time_str = scheduled_time_str.replace('Z', '+00:00')
                    elif '+' not in scheduled_time_str and '-' not in scheduled_time_str:
                        scheduled_time_str = scheduled_time_str + '+00:00'

                    # 予約時間をUTCのdatetimeオブジェクトに変換
                    scheduled_dt = datetime.datetime.fromisoformat(scheduled_time_str)
                    scheduled_dt = ensure_utc(scheduled_dt)
                    time_diff = (scheduled_dt - now).total_seconds()

                    logger.info(f"投稿ID: {post.id}, 予約時間: {scheduled_dt.isoformat()}, 現在時刻との差: {time_diff}秒")

                    # 過去の予約時間の投稿のみを処理対象に追加
                    if time_diff <= 0:
                        post_dict = {
                            'id': post.id,
                            'content': post.content,
                            'platforms': post.platforms,
                            'scheduled_time': scheduled_dt.isoformat(),
                            'status': post.status,
                            'created_at': post.created_at,
                            'media_paths': post.media_paths,
                            'post_mode': post.post_mode
                        }
                        result_posts.append(post_dict)
                        logger.info(f"処理対象の投稿を追加: ID={post.id}, 予約時間={scheduled_dt.isoformat()}")
                except (ValueError, TypeError) as e:
                    logger.error(f"日時変換エラー: {e}, 投稿ID={post.id}, 時間文字列={post.scheduled_time}")

            return result_posts
        except Exception as e:
            logger.error(f"予約投稿取得エラー: {e}")
            return []

    def update_post_status(self, post_id, status):
        try:
            post = self.session.query(ScheduledPost).filter(ScheduledPost.id == post_id).first()
            if post:
                post.status = status
                self.session.commit()
                logger.info(f"投稿ステータスを更新しました: ID={post_id}, ステータス={status}")
            else:
                logger.warning(f"投稿が見つかりません: ID={post_id}")
        except Exception as e:
            self.session.rollback()
            logger.error(f"ステータス更新エラー: {e}")

    def get_all_scheduled_posts(self):
        try:
            posts = self.session.query(ScheduledPost).order_by(ScheduledPost.scheduled_time.desc()).all()
            logger.info(f"全投稿数: {len(posts)}")

            # 辞書形式に変換
            result_posts = []
            for post in posts:
                try:
                    # UTCの時間をJSTに変換
                    scheduled_dt = datetime.datetime.fromisoformat(post.scheduled_time.replace('Z', '+00:00'))
                    scheduled_dt = ensure_utc(scheduled_dt)
                    scheduled_jst = utc_to_jst(scheduled_dt)

                    post_dict = {
                        'id': post.id,
                        'content': post.content,
                        'platforms': post.platforms,
                        'scheduled_time': scheduled_jst.isoformat(),  # JSTで表示
                        'status': post.status,
                        'created_at': post.created_at,
                        'media_paths': post.media_paths
                    }
                    result_posts.append(post_dict)
                except (ValueError, TypeError) as e:
                    logger.error(f"日時変換エラー: {e}, 投稿ID={post.id}")

            return result_posts
        except Exception as e:
            logger.error(f"投稿一覧取得エラー: {e}")
            return []

    def delete_scheduled_post(self, post_id):
        try:
            post = self.session.query(ScheduledPost).filter(ScheduledPost.id == post_id).first()
            if post:
                self.session.delete(post)
                self.session.commit()
                logger.info(f"投稿を削除しました: ID={post_id}")
            else:
                logger.warning(f"投稿が見つかりません: ID={post_id}")
        except Exception as e:
            self.session.rollback()
            logger.error(f"投稿削除エラー: {e}")

    def __del__(self):
        """セッションのクリーンアップ"""
        self.session.close()
