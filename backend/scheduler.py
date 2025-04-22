import time
import threading
import datetime
import json
import os
import logging
from models import ScheduledPostDB, ensure_utc, utc_to_jst
from utils import sns_client

# ロガーの設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("PostScheduler")

class PostScheduler:
    def __init__(self, check_interval=3600):
        try:
            self.db = ScheduledPostDB()
            logger.info("スケジューラーのデータベース初期化成功")
        except Exception as e:
            logger.error(f"スケジューラーのデータベース初期化エラー: {e}")
            raise

        self.check_interval = check_interval  # 1h単位で確認間隔を設定
        self.running = False
        self.thread = None

    def start(self):
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._scheduler_loop)
            self.thread.daemon = True
            self.thread.start()
            logger.info("投稿スケジューラを開始しました")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()
            logger.info("投稿スケジューラを停止しました")

    def _get_platform_content(self, content, platform, platform_content, post_mode):
        """プラットフォームごとの投稿コンテンツを取得する"""
        try:
            logger.info(f"コンテンツタイプ: {type(content)}, 投稿モード: {post_mode}")
            logger.info(f"プラットフォームコンテンツ: {platform_content}")

            # プラットフォームのcontentがすでに文字列の場合はそのまま使用
            if isinstance(platform_content, dict) and 'content' in platform_content:
                platform_content = platform_content['content']
                logger.info(f"プラットフォーム情報からコンテンツを取得しました: {platform_content[:50]}...")
                return platform_content

            # 個別投稿モードの場合
            if post_mode == 'individual':
                # contentが辞書で、そのプラットフォームのキーがある場合
                if isinstance(content, dict) and platform in content:
                    platform_content = content[platform]
                    logger.info(f"個別モード: {platform}用のコンテンツを使用しました")
                    return platform_content
            # 一括投稿モードの場合
            elif post_mode == 'unified':
                # contentが文字列の場合
                if isinstance(content, str):
                    logger.info(f"一括モード: 共通コンテンツ(文字列)を使用しました")
                    return content
                # contentが辞書で'text'キーがある場合
                elif isinstance(content, dict) and 'text' in content:
                    logger.info(f"一括モード: 'text'キーからコンテンツを使用しました")
                    return content['text']
                # contentがそのまま使える場合
                else:
                    logger.info(f"一括モード: コンテンツを文字列化して使用しました")
                    return str(content)

            # プラットフォームのコンテンツを直接取得できない場合は、platforms情報から取得する
            logger.error(f"プラットフォーム {platform} のコンテンツが見つかりません")
            return None
        except Exception as e:
            logger.error(f"コンテンツ取得エラー: {e}")
            return None

    def _scheduler_loop(self):
        while self.running:
            try:
                logger.info("スケジューラーがチェックしています...")

                # 現在時刻をUTCで取得
                now = ensure_utc(datetime.datetime.now())
                logger.info(f"現在時刻(UTC): {now.isoformat()}")
                logger.info(f"現在時刻(JST): {utc_to_jst(now).isoformat()}")

                # 投稿予定時刻が現在時刻以前のpending状態の投稿を取得
                pending_posts = self.db.get_pending_posts()
                logger.info(f"保留中の投稿数: {len(pending_posts)}")

                for post in pending_posts:
                    try:
                        logger.info(f"スケジュールされた投稿を処理中: ID={post['id']}, 時刻={post['scheduled_time']}")

                        # 投稿データの準備
                        try:
                            # JSONデータのデコード
                            platforms = json.loads(post['platforms']) if isinstance(post['platforms'], str) else post['platforms']
                            content = post['content']

                            logger.info(f"投稿プラットフォーム: {list(platforms.keys())}")
                            logger.info(f"投稿内容の長さ: {len(str(content))}")

                            post_data = {}
                            for platform, platform_content in platforms.items():
                                if isinstance(platform_content, dict) and platform_content.get('selected'):
                                    post_data[platform] = platform_content
                                    logger.info(f"{platform}への投稿が選択されています")

                            if not post_data:
                                logger.error(f"投稿先のプラットフォームが選択されていません: ID={post['id']}")
                                self.db.update_post_status(post['id'], 'failed')
                                continue

                            # 投稿モードの取得
                            post_mode = post.get('post_mode', 'unified')
                            logger.info(f"投稿モード: {post_mode}")

                            # メディアパスを取得
                            media_paths = json.loads(post['media_paths']) if post.get('media_paths') else None
                            if media_paths:
                                logger.info(f"メディアファイル: {media_paths}")

                            # SNSへの投稿実行
                            success = True
                            for platform, content_data in post_data.items():
                                try:
                                    # プラットフォームのコンテンツを取得
                                    # content_dataに'content'フィールドがあれば、それを先にチェック
                                    if isinstance(content_data, dict) and 'content' in content_data:
                                        platform_content = content_data['content']
                                        logger.info(f"プラットフォーム情報から直接コンテンツを取得: {platform_content[:50] if platform_content else 'None'}")
                                    else:
                                        # コンテンツ取得メソッドを使用
                                        platform_content = self._get_platform_content(content, platform, content_data, post_mode)
                                        logger.info(f"取得したコンテンツ: {platform_content[:50] if platform_content else 'None'}")
                                        if not platform_content:
                                            logger.error(f"プラットフォーム {platform} のコンテンツが空です")
                                            success = False
                                            continue

                                        if media_paths and media_paths.get('files'):
                                            result = sns_client.post_with_media_to_platform(
                                                platform,
                                                platform_content,
                                                media_paths['files']
                                            )
                                        else:
                                            result = sns_client.post_to_platform(platform, platform_content)

                                        if not result.get('success'):
                                            logger.error(f"プラットフォーム {platform} への投稿に失敗: {result.get('error')}")
                                            success = False
                                        else:
                                            logger.info(f"プラットフォーム {platform} への投稿に成功")

                                except Exception as e:
                                    logger.error(f"プラットフォーム {platform} への投稿でエラー発生: {e}")
                                    success = False

                            # 投稿状態の更新
                            final_status = 'completed' if success else 'failed'
                            self.db.update_post_status(post['id'], final_status)
                            logger.info(f"投稿ID {post['id']} の状態を {final_status} に更新しました")

                        except json.JSONDecodeError as e:
                            logger.error(f"JSONデコードエラー: {e}")
                            self.db.update_post_status(post['id'], 'failed')
                        except Exception as e:
                            logger.error(f"投稿処理中の予期せぬエラー: {e}")
                            self.db.update_post_status(post['id'], 'failed')

                    except Exception as e:
                        logger.error(f"投稿処理中の重大なエラー: {e}")
                        try:
                            self.db.update_post_status(post['id'], 'failed')
                        except:
                            pass

                time.sleep(self.check_interval)

            except Exception as e:
                logger.error(f"スケジューラーループでエラー発生: {e}")
                time.sleep(self.check_interval)
