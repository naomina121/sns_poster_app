import os
import json
import requests
from atproto import Client as AtprotoClient, models
import tweepy
from mastodon import Mastodon
import misskey
from dotenv import load_dotenv
import mimetypes
import cloudinary
import cloudinary.uploader
import ulid
import sys
from datetime import datetime


# .envファイルから環境変数を読み込む
load_dotenv()

# cloudinary
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")

# cloudinary upload
def upload_media(image_path):
    cloudinary.config(
        cloud_name=CLOUDINARY_CLOUD_NAME,
        api_key=CLOUDINARY_API_KEY,
        api_secret=CLOUDINARY_API_SECRET,
        secure=True,
    )

    upload_result = cloudinary.uploader.upload(
        image_path, public_id=f"threads/{ulid.new()}"
    )
    return upload_result["secure_url"]

# 文字数制限の定義
CHARACTER_LIMITS = {
    "bluesky": 300,
    "x": 280,
    "threads": 500,
    "misskey": 3000,
    "mastodon": 500
}

def get_character_limits():
    """文字数制限を取得する関数"""
    return CHARACTER_LIMITS


class SnsClient:
    def __init__(self):
        """SNSクライアントの初期化"""
        self.clients = {}
        self.setup_clients()

    def setup_clients(self):
        """各SNSクライアントのセットアップ"""
        # Blueskyのセットアップ
        try:
            bluesky_username = os.getenv("BLUESKY_USERNAME")
            bluesky_password = os.getenv("BLUESKY_PASSWORD")
            if bluesky_username and bluesky_password:
                bluesky_client = AtprotoClient()
                bluesky_client.login(bluesky_username, bluesky_password)
                self.clients["bluesky"] = bluesky_client
        except Exception as e:
            print(f"Bluesky setup error: {e}")

        # X/Twitterのセットアップ
        try:
            x_api_key = os.getenv("X_API_KEY")
            x_api_secret = os.getenv("X_API_SECRET")
            x_access_token = os.getenv("X_ACCESS_TOKEN")
            x_access_token_secret = os.getenv("X_ACCESS_TOKEN_SECRET")

            if all([x_api_key, x_api_secret, x_access_token, x_access_token_secret]):
                # APIクライアント（V2）
                client = tweepy.Client(
                    consumer_key=x_api_key,
                    consumer_secret=x_api_secret,
                    access_token=x_access_token,
                    access_token_secret=x_access_token_secret
                )

                # メディアアップロード用のv1.1 APIも設定
                auth = tweepy.OAuth1UserHandler(
                    x_api_key, x_api_secret, x_access_token, x_access_token_secret
                )
                api_v1 = tweepy.API(auth)

                self.clients["x"] = {
                    "client": client,
                    "api_v1": api_v1
                }
        except Exception as e:
            print(f"X/Twitter setup error: {e}")

        # Threadsのセットアップ
        try:
            threads_access_token = os.getenv("THREADS_ACCESS_TOKEN")
            if threads_access_token:
                self.clients["threads"] = threads_access_token
        except Exception as e:
            print(f"Threads setup error: {e}")

        # Misskeyのセットアップ
        try:
            misskey_token = os.getenv("MISSKEY_API_TOKEN")
            misskey_instance = os.getenv("MISSKEY_INSTANCE_URL")
            if misskey_token and misskey_instance:
                misskey_client = misskey.Misskey(misskey_instance, i=misskey_token)
                self.clients["misskey"] = misskey_client
        except Exception as e:
            print(f"Misskey setup error: {e}")

        # Mastodonのセットアップ
        try:
            mastodon_token = os.getenv("MASTODON_ACCESS_TOKEN")
            mastodon_instance = os.getenv("MASTODON_INSTANCE_URL")
            if mastodon_token and mastodon_instance:
                mastodon_client = Mastodon(
                    access_token=mastodon_token,
                    api_base_url=mastodon_instance
                )
                self.clients["mastodon"] = mastodon_client
        except Exception as e:
            print(f"Mastodon setup error: {e}")

    def post_to_bluesky(self, content):
        """Blueskyに投稿する関数"""
        try:
            if "bluesky" in self.clients:
                bluesky_username = os.getenv("BLUESKY_USERNAME")
                bluesky_password = os.getenv("BLUESKY_PASSWORD")
                if bluesky_username and bluesky_password:
                    bluesky_client = AtprotoClient()
                    bluesky_client.login(bluesky_username, bluesky_password)
                    response = bluesky_client.send_post(content)
                    return {"success": True, "response": "投稿成功"}
                else:
                    return {"success": False, "error": "Blueskyのユーザー名とパスワードが設定されていません"}
            return {"success": False, "error": "Blueskyクライアントが設定されていません"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def post_to_x(self, content):
        """X/Twitterに投稿する関数"""
        try:
            if "x" in self.clients:
                response = self.clients["x"]["client"].create_tweet(text=content)
                return {"success": True, "response": "投稿成功"}
            return {"success": False, "error": "Xクライアントが設定されていません"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def post_to_threads(self, content):
        """Threadsに投稿する関数"""
        try:
            if "threads" in self.clients:
                access_token = self.clients["threads"]
                api_base_url = "https://graph.threads.net/v1.0"

                # ユーザーIDを取得
                user_url = f"{api_base_url}/me"
                user_headers = {"Authorization": f"Bearer {access_token}"}
                user_response = requests.get(user_url, headers=user_headers)

                if user_response.ok:
                    user_id = user_response.json().get("id")

                    # 投稿を作成
                    create_url = f"{api_base_url}/{user_id}/threads"
                    create_data = {"text": content, "media_type": "TEXT"}
                    create_headers = {
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json"
                    }
                    response = requests.post(create_url, json=create_data, headers=create_headers)

                    if response.ok:
                        creation_id = response.json().get("id")

                        # 投稿を公開
                        publish_url = f"{api_base_url}/{user_id}/threads_publish"
                        publish_data = {"creation_id": creation_id}
                        publish_headers = {
                            "Authorization": f"Bearer {access_token}",
                            "Content-Type": "application/json"
                        }
                        publish_response = requests.post(publish_url, json=publish_data, headers=publish_headers)

                        if publish_response.ok:
                            return {"success": True, "response": "投稿成功"}

                return {"success": False, "error": "Threads APIの呼び出しに失敗しました"}
            return {"success": False, "error": "Threadsクライアントが設定されていません"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def post_to_misskey(self, content):
        """Misskeyに投稿する関数"""
        try:
            if "misskey" in self.clients:
                note = self.clients["misskey"].notes_create(text=content)
                return {"success": True, "response": "投稿成功"}
            return {"success": False, "error": "Misskeyクライアントが設定されていません"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def post_to_mastodon(self, content):
        """Mastodonに投稿する関数"""
        try:
            if "mastodon" in self.clients:
                status = self.clients["mastodon"].status_post(content)
                return {"success": True, "response": "投稿成功"}
            return {"success": False, "error": "Mastodonクライアントが設定されていません"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def post_to_platform(self, platform, content):
        """指定のプラットフォームに投稿する"""
        if platform == "bluesky":
            return self.post_to_bluesky(content)
        elif platform == "x":
            return self.post_to_x(content)
        elif platform == "threads":
            return self.post_to_threads(content)
        elif platform == "misskey":
            return self.post_to_misskey(content)
        elif platform == "mastodon":
            return self.post_to_mastodon(content)
        else:
            return {"success": False, "error": f"未対応のプラットフォーム: {platform}"}

    def upload_media_to_x(self, file_path):
        """X/Twitterにメディアをアップロードする関数"""
        try:
            if "x" in self.clients:
                # V1.1 APIを使用してメディアをアップロード
                media = self.clients["x"]["api_v1"].media_upload(file_path)
                return {
                    "success": True,
                    "media_id": media.media_id
                }

            return {"success": False, "error": "Xクライアントが設定されていません"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def upload_media_to_threads(self,content, file_path):
        """Threadsにメディアをアップロードする関数 (cloudinaryを使用)"""
        try:
            if "threads" in self.clients:
                access_token = self.clients["threads"]
                api_base_url = "https://graph.threads.net/v1.0"

                # ユーザーIDを取得
                user_url = f"{api_base_url}/me"
                user_headers = {"Authorization": f"Bearer {access_token}"}
                user_response = requests.get(user_url, headers=user_headers)

                if user_response.ok:
                    user_id = user_response.json().get("id")

                    # 投稿を作成
                    create_url = f"{api_base_url}/{user_id}/threads"
                    create_data = {"text": content, "media_type": "IMAGE", "image_url": upload_media(file_path)}
                    create_headers = {
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json"
                    }
                    response = requests.post(create_url, json=create_data, headers=create_headers)

                    if response.ok:
                        creation_id = response.json().get("id")

                        # 投稿を公開
                        publish_url = f"{api_base_url}/{user_id}/threads_publish"
                        publish_data = {"creation_id": creation_id}
                        publish_headers = {
                            "Authorization": f"Bearer {access_token}",
                            "Content-Type": "application/json"
                        }
                        publish_response = requests.post(publish_url, json=publish_data, headers=publish_headers)

                        if publish_response.ok:
                            return {
                                "success": True,
                                "file_id": creation_id
                            }

                return {"success": False, "error": "Threads APIの呼び出しに失敗しました"}
            return {"success": False, "error": "Threadsクライアントが設定されていません"}
        except Exception as e:
            return {"success": False, "error": str(e)}


    def upload_media_to_misskey(self, file_path):
        """Misskeyにメディアをアップロードする関数"""
        try:
            if "misskey" in self.clients:
                with open(file_path, 'rb') as f:
                    file_data = f.read()

                # MIMEタイプを取得
                mime_type, _ = mimetypes.guess_type(file_path)
                if not mime_type:
                    # デフォルトのMIMEタイプを設定
                    if file_path.lower().endswith(('.jpg', '.jpeg')):
                        mime_type = 'image/jpeg'
                    elif file_path.lower().endswith('.png'):
                        mime_type = 'image/png'
                    elif file_path.lower().endswith('.gif'):
                        mime_type = 'image/gif'
                    elif file_path.lower().endswith(('.mp4', '.mov')):
                        mime_type = 'video/mp4'
                    else:
                        mime_type = 'application/octet-stream'

                # ファイル名の取得
                file_name = os.path.basename(file_path)

                # Misskeyにドライブファイルとしてアップロード
                drive_file = self.clients["misskey"].drive_files_create(
                    file=file_data,
                    name=file_name,
                    force=False
                )

                return {
                    "success": True,
                    "file_id": drive_file["id"]
                }

            return {"success": False, "error": "Misskeyクライアントが設定されていません"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def upload_media_to_mastodon(self, file_path):
        """Mastodonにメディアをアップロードする関数"""
        try:
            if "mastodon" in self.clients:
                # Mastodonにメディアをアップロード
                media = self.clients["mastodon"].media_post(
                    media_file=file_path,
                    description="Uploaded from SNS Poster App"
                )

                return {
                    "success": True,
                    "media_id": media["id"]
                }

            return {"success": False, "error": "Mastodonクライアントが設定されていません"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def post_with_media_to_bluesky(self, content, media_files):
        """Blueskyにメディア付きで投稿する関数"""
        try:
            if "bluesky" in self.clients:
                if not media_files or len(media_files) == 0:
                    return self.post_to_bluesky(content)

                bluesky_client = AtprotoClient()
                bluesky_username = os.getenv("BLUESKY_USERNAME")
                bluesky_password = os.getenv("BLUESKY_PASSWORD")
                bluesky_client.login(bluesky_username, bluesky_password)

                if not bluesky_client.me.did:
                    return {"success": False, "error": "Blueskyの認証情報が設定されていません"}


                # メディアファイルのディレクトリパスを取得
                # media_filesは配列で渡されるため、最初のファイルのディレクトリを取得
                first_file_path = media_files[0]
                image_dir_path = os.path.dirname(first_file_path)

                # ディレクトリ内の画像ファイルを取得
                image_files = []
                for filename in os.listdir(image_dir_path):
                    if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                        image_files.append(os.path.join(image_dir_path, filename))

                if not image_files:
                    return {"success": False, "error": "有効な画像ファイルが見つかりません"}

                # メディアをアップロード
                with open(image_files[0], 'rb') as f:
                    img_data = f.read()

                    upload = bluesky_client.upload_blob(img_data)
                    images = [models.AppBskyEmbedImages.Image(alt=f.name, image=upload.blob)]
                    embed = models.AppBskyEmbedImages.Main(images=images)

                    bluesky_client.com.atproto.repo.create_record(
                        models.ComAtprotoRepoCreateRecord.Data(
                            repo=bluesky_client.me.did,
                            collection=models.ids.AppBskyFeedPost,
                            record=models.AppBskyFeedPost.Record(
                                created_at=bluesky_client.get_current_time_iso(), text=content, embed=embed
                            ),
                        )
                    )

                    return {"success": True, "response": "メディア付き投稿成功"}

            return {"success": False, "error": "Blueskyクライアントが設定されていません"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def post_with_media_to_x(self, content, media_files):
        """X/Twitterにメディア付きで投稿する関数"""
        try:
            if "x" in self.clients:
                if not media_files or len(media_files) == 0:
                    return self.post_to_x(content)

                # 最大4つのメディアをアップロード
                media_ids = []
                for file_path in media_files[:4]:  # X/Twitterは最大4つのメディアをサポート
                    media_result = self.upload_media_to_x(file_path)
                    if media_result["success"]:
                        media_ids.append(media_result["media_id"])

                if not media_ids:
                    return {"success": False, "error": "現在のThreadsではメディア投稿に対応されてないようです。"}

                # メディア付き投稿
                response = self.clients["x"]["client"].create_tweet(
                    text=content,
                    media_ids=media_ids
                )

                return {"success": True, "response": "メディア付き投稿成功"}

            return {"success": False, "error": "Xクライアントが設定されていません"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def post_with_media_to_threads(self, content, media_files):
        """Threadsにメディア付きで投稿する関数"""
        try:
            if "threads" in self.clients:
                if not media_files or len(media_files) == 0:
                    return self.post_to_threads(content)

                # メディアをアップロード
                file_ids = []
                for file_path in media_files:
                    media_result = self.upload_media_to_threads(content,file_path)
                    if media_result["success"]:
                        file_ids.append(media_result["file_id"])

                if not file_ids:
                    return {"success": False, "error": "メディアのアップロードに失敗しました"}

                return {"success": True, "response": "メディア付き投稿成功"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def post_with_media_to_misskey(self, content, media_files):
        """Misskeyにメディア付きで投稿する関数"""
        try:
            if "misskey" in self.clients:
                if not media_files or len(media_files) == 0:
                    return self.post_to_misskey(content)

                # メディアをアップロード
                file_ids = []
                for file_path in media_files:
                    media_result = self.upload_media_to_misskey(file_path)
                    if media_result["success"]:
                        file_ids.append(media_result["file_id"])

                if not file_ids:
                    return {"success": False, "error": "メディアのアップロードに失敗しました"}

                # メディア付き投稿
                note = self.clients["misskey"].notes_create(
                    text=content,
                    file_ids=file_ids
                )

                return {"success": True, "response": "メディア付き投稿成功"}

            return {"success": False, "error": "Misskeyクライアントが設定されていません"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def post_with_media_to_mastodon(self, content, media_files):
        """Mastodonにメディア付きで投稿する関数"""
        try:
            if "mastodon" in self.clients:
                if not media_files or len(media_files) == 0:
                    return self.post_to_mastodon(content)

                # メディアをアップロード（最大4つ）
                media_ids = []
                for file_path in media_files[:4]:  # Mastodonは通常4つまでのメディアをサポート
                    media_result = self.upload_media_to_mastodon(file_path)
                    if media_result["success"]:
                        media_ids.append(media_result["media_id"])

                if not media_ids:
                    return {"success": False, "error": "メディアのアップロードに失敗しました"}

                # メディア付き投稿
                status = self.clients["mastodon"].status_post(
                    content,
                    media_ids=media_ids
                )

                return {"success": True, "response": "メディア付き投稿成功"}

            return {"success": False, "error": "Mastodonクライアントが設定されていません"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def post_with_media_to_platform(self, platform, content, media_files):
        """指定プラットフォームにメディア付きで投稿する関数"""
        if platform == "bluesky":
            return self.post_with_media_to_bluesky(content, media_files)
        elif platform == "x":
            return self.post_with_media_to_x(content, media_files)
        elif platform == "threads":
            return self.post_with_media_to_threads(content, media_files)
        elif platform == "misskey":
            return self.post_with_media_to_misskey(content, media_files)
        elif platform == "mastodon":
            return self.post_with_media_to_mastodon(content, media_files)
        else:
            return {"success": False, "error": f"未対応のプラットフォーム: {platform}"}

    def post_to_platforms(self, posts):
        """複数のプラットフォームに投稿する関数

        Args:
            posts: プラットフォーム名をキー、プラットフォーム情報を値とする辞書

        Returns:
            各プラットフォームの投稿結果を含む辞書
        """
        results = {}

        for platform, content_data in posts.items():
            if isinstance(content_data, dict) and content_data.get("content"):
                results[platform] = self.post_to_platform(platform, content_data["content"])
            elif isinstance(content_data, str) and content_data:
                results[platform] = self.post_to_platform(platform, content_data)

        return results

# SNSクライアントのインスタンス
sns_client = SnsClient()
