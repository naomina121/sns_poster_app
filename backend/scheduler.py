import time
import threading
import datetime
import json
import os
import logging
from models import ScheduledPostDB
from utils import sns_client

# ロガーの設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("PostScheduler")

class PostScheduler:
    def __init__(self, check_interval=60):
        try:
            self.db = ScheduledPostDB()
            logger.info("スケジューラーのデータベース初期化成功")
        except Exception as e:
            logger.error(f"スケジューラーのデータベース初期化エラー: {e}")
            raise

        self.check_interval = check_interval  # 分単位で確認間隔を設定
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

    def _scheduler_loop(self):
        while self.running:
            try:
                logger.info("スケジューラーがチェックしています...")

                # 現在時刻を表示
                now = datetime.datetime.now()
                logger.info(f"現在時刻: {now.isoformat()}")

                # 投稿予定時刻が現在時刻以前のpending状態の投稿を取得
                pending_posts = self.db.get_pending_posts()

                logger.info(f"保留中の投稿数: {len(pending_posts)}")

                # すべての投稿を確認してデバッグ（問題解決用）
                all_posts = self.db.get_all_scheduled_posts()
                logger.info(f"データベース内の全投稿数: {len(all_posts)}")
                for post in all_posts:
                    try:
                        post_id = post.get('id', 'unknown')
                        scheduled_time = post.get('scheduled_time', 'unknown')
                        status = post.get('status', 'unknown')

                        # 予約時間をdatetimeオブジェクトに変換して比較
                        try:
                            scheduled_dt = datetime.datetime.fromisoformat(scheduled_time)
                            time_diff = (scheduled_dt - now).total_seconds()
                            is_past = time_diff <= 0

                            logger.info(f"投稿ID: {post_id}, 予約時間: {scheduled_time}, ステータス: {status}, 過去の時間: {is_past}, 時間差: {time_diff}秒")
                        except (ValueError, TypeError) as e:
                            logger.error(f"日時変換エラー: {e}, 投稿ID: {post_id}, 時間文字列: {scheduled_time}")
                    except Exception as e:
                        logger.error(f"投稿情報取得エラー: {e}")

                for post in pending_posts:
                    logger.info(f"スケジュールされた投稿を処理中: ID={post['id']}, 時刻={post['scheduled_time']}")

                    # 投稿データの準備
                    try:
                        # JSONデータのデコード
                        try:
                            platforms = json.loads(post['platforms']) if isinstance(post['platforms'], str) else post['platforms']
                        except (json.JSONDecodeError, TypeError) as e:
                            logger.error(f"プラットフォームデータのデコードエラー: {e}")
                            platforms = {}

                        try:
                            content = json.loads(post['content']) if isinstance(post['content'], str) else post['content']
                        except (json.JSONDecodeError, TypeError) as e:
                            logger.error(f"コンテンツデータのデコードエラー: {e}")
                            content = ""

                        post_data = {}

                        # メディアパスを取得（存在する場合）
                        try:
                            media_paths = json.loads(post['media_paths']) if post['media_paths'] else None
                        except (json.JSONDecodeError, TypeError) as e:
                            logger.error(f"メディアパスデータのデコードエラー: {e}")
                            media_paths = None

                        # プラットフォームごとに投稿データを準備
                        for platform, platform_content in platforms.items():
                            if isinstance(platform_content, dict) and platform_content.get('selected'):
                                post_data[platform] = platform_content

                        if not post_data:
                            logger.error(f"投稿先のプラットフォームが選択されていません: ID={post['id']}")
                            self.db.update_post_status(post['id'], 'failed')
                            continue

                        # SNSへの投稿実行
                        results = {}

                        # メディアのある投稿の場合
                        if media_paths and media_paths.get('files'):
                            media_files = media_paths.get('files', [])

                            # パス検証
                            valid_files = []
                            for file_path in media_files:
                                if os.path.exists(file_path):
                                    valid_files.append(file_path)
                                else:
                                    logger.warning(f"ファイルが存在しません: {file_path}")

                            if not valid_files and media_files:
                                logger.error(f"有効なメディアファイルがありません: ID={post['id']}")
                                self.db.update_post_status(post['id'], 'failed')
                                continue

                            for platform, content_data in post_data.items():
                                try:
                                    # メディアをアップロードしてから投稿
                                    platform_content = content_data.get('content', '')
                                    result = sns_client.post_with_media_to_platform(
                                        platform,
                                        platform_content,
                                        valid_files
                                    )
                                    results[platform] = result
                                    logger.info(f"プラットフォーム {platform} への投稿結果: {result}")
                                except Exception as e:
                                    error_msg = f"プラットフォーム {platform} への投稿エラー: {e}"
                                    logger.error(error_msg)
                                    results[platform] = {"success": False, "error": str(e)}
                        else:
                            # 通常のテキスト投稿
                            for platform, content_data in post_data.items():
                                try:
                                    platform_content = content_data.get('content', '')
                                    result = sns_client.post_to_platform(platform, platform_content)
                                    results[platform] = result
                                    logger.info(f"プラットフォーム {platform} への投稿結果: {result}")
                                except Exception as e:
                                    error_msg = f"プラットフォーム {platform} への投稿エラー: {e}"
                                    logger.error(error_msg)
                                    results[platform] = {"success": False, "error": str(e)}

                        # 全てのプラットフォームへの投稿が成功したかチェック
                        success_results = [r.get('success', False) for r in results.values()]
                        if success_results and all(success_results):
                            self.db.update_post_status(post['id'], 'completed')
                            logger.info(f"予約投稿完了: ID={post['id']}")
                        else:
                            failed_platforms = [p for p, r in results.items() if not r.get('success', False)]
                            logger.error(f"一部のプラットフォームへの投稿に失敗: {failed_platforms}")
                            self.db.update_post_status(post['id'], 'failed')
                    except Exception as e:
                        logger.error(f"投稿処理エラー: {e}")
                        self.db.update_post_status(post['id'], 'failed')

            except Exception as e:
                logger.error(f"スケジューラーエラー: {e}")

            # 次のチェックまで待機
            time.sleep(self.check_interval)
