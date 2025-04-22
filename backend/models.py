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
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@postgres:5432/sns_poster")
logger.info(f"データベース接続URL: {DATABASE_URL}")

# SQLAlchemyの設定
engine = create_engine(DATABASE_URL)
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
        self.db_path = DATABASE_URL  # SQLite互換のために属性を残す
        self.session = Session()

    def add_scheduled_post(self, content, platforms, scheduled_time, media_paths=None):
        try:
            now = datetime.datetime.now().isoformat()

            # 予約時間のフォーマットを標準化
            try:
                # 日時文字列をdatetimeオブジェクトに変換
                scheduled_dt = datetime.datetime.fromisoformat(scheduled_time)
                # ISO形式に変換して保存
                scheduled_time_iso = scheduled_dt.isoformat()
                logger.info(f"予約時間を標準化: 元の形式={scheduled_time}, 標準化={scheduled_time_iso}")
            except (ValueError, TypeError) as e:
                logger.error(f"予約時間の変換に失敗しました: {e}")
                # エラーの場合は元の形式のまま使用
                scheduled_time_iso = scheduled_time

            # オブジェクトをJSON文字列に変換
            if isinstance(content, (dict, list)):
                content = json.dumps(content, ensure_ascii=False)
            if isinstance(platforms, (dict, list)):
                platforms = json.dumps(platforms, ensure_ascii=False)
            if isinstance(media_paths, (dict, list)):
                media_paths = json.dumps(media_paths, ensure_ascii=False)

            logger.info(f"保存するコンテンツ: {content}")
            logger.info(f"保存するプラットフォーム: {platforms}")
            logger.info(f"保存するメディアパス: {media_paths}")
            logger.info(f"保存する予約時間: {scheduled_time_iso}")

            new_post = ScheduledPost(
                content=content,
                platforms=platforms,
                scheduled_time=scheduled_time_iso,
                created_at=now,
                media_paths=media_paths
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
            now = datetime.datetime.now()
            now_iso = now.isoformat()
            logger.info(f"現在時刻（データベース検索用）: {now_iso}")

            # まずすべての投稿を取得して時間を表示
            all_posts = self.session.query(ScheduledPost).all()
            for post in all_posts:
                logger.info(f"投稿情報: ID={post.id}, 時間={post.scheduled_time}, ステータス={post.status}")
                try:
                    # 予約時間をdatetimeオブジェクトに変換して比較
                    scheduled_dt = datetime.datetime.fromisoformat(post.scheduled_time)
                    time_diff = (scheduled_dt - now).total_seconds()
                    is_past = time_diff <= 0
                    logger.info(f"  投稿の予約時間分析: 過去の時間={is_past}, 時間差={time_diff}秒")
                except (ValueError, TypeError) as e:
                    logger.error(f"  日時変換エラー: {e}")

            # ステータスが'pending'の投稿を全て取得
            posts = []
            for post in all_posts:
                if post.status == 'pending':
                    logger.info(f"処理対象の投稿を追加: ID={post.id}, 予約時間={post.scheduled_time}")
                    posts.append(post)

            # 辞書形式に変換
            result_posts = []
            for post in posts:
                post_dict = {
                    'id': post.id,
                    'content': post.content,
                    'platforms': post.platforms,
                    'scheduled_time': post.scheduled_time,
                    'status': post.status,
                    'created_at': post.created_at,
                    'media_paths': post.media_paths
                }
                result_posts.append(post_dict)

            if result_posts:
                logger.info(f"条件に合致する投稿が{len(result_posts)}件見つかりました")
            else:
                logger.info("条件に合致する投稿はありません")

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
                post_dict = {
                    'id': post.id,
                    'content': post.content,
                    'platforms': post.platforms,
                    'scheduled_time': post.scheduled_time,
                    'status': post.status,
                    'created_at': post.created_at,
                    'media_paths': post.media_paths
                }
                result_posts.append(post_dict)

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
