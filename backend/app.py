import os
import json
import uuid
import logging
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
from utils import sns_client, get_character_limits
from models import ScheduledPostDB, create_tables
from scheduler import PostScheduler
from dotenv import load_dotenv
from sqlalchemy import update
from models import ScheduledPost, engine

# ロガーの設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("FlaskApp")

# .envファイルから環境変数を読み込む
load_dotenv()

# データベースの初期化
create_tables()
logger.info("データベーステーブルを初期化しました")

app = Flask(__name__, static_folder='../frontend', static_url_path='')
CORS(app)  # CORS設定を有効に

# Flaskの秘密鍵を設定
app.secret_key = os.getenv("FLASK_SECRET_KEY", "default_secret_key")

# アップロードされたファイルの保存先
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# 許可するファイル拡張子
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'webp'}

# ファイル拡張子のチェック関数
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# 投稿スケジューラーを起動
scheduler = PostScheduler()
scheduler.start()

@app.route('/')
def index():
    """フロントエンドのindex.htmlを返す"""
    return send_from_directory('../frontend', 'index.html')

@app.route('/api/platforms', methods=['GET'])
def get_platforms():
    """利用可能なプラットフォームの一覧と文字数制限を返す"""
    platforms = {
        "bluesky": {"enabled": "bluesky" in sns_client.clients, "limit": get_character_limits()["bluesky"]},
        "x": {"enabled": "x" in sns_client.clients, "limit": get_character_limits()["x"]},
        "threads": {"enabled": "threads" in sns_client.clients, "limit": get_character_limits()["threads"]},
        "misskey": {"enabled": "misskey" in sns_client.clients, "limit": get_character_limits()["misskey"]},
        "mastodon": {"enabled": "mastodon" in sns_client.clients, "limit": get_character_limits()["mastodon"]}
    }
    return jsonify(platforms)

@app.route('/api/post', methods=['POST'])
def post_to_sns():
    """選択されたSNSに投稿する"""
    data = request.json

    if not data:
        return jsonify({"success": False, "error": "データが送信されていません"}), 400

    posts = {}
    post_mode = data.get('post_mode', 'unified')

    if post_mode == 'unified':
        # 一括モードの場合
        content = data.get('content', '')
        if not content:
            return jsonify({"success": False, "error": "投稿内容が空です"}), 400

        for platform in ["bluesky", "x", "threads", "misskey", "mastodon"]:
            if platform in data and data[platform]["selected"]:
                posts[platform] = content
    else:
        # 個別モードの場合
        for platform in ["bluesky", "x", "threads", "misskey", "mastodon"]:
            if platform in data and data[platform]["selected"]:
                posts[platform] = data[platform]["content"]

    if not posts:
        return jsonify({"success": False, "error": "投稿先のSNSが選択されていません"}), 400

    # 各プラットフォームに投稿
    try:
        results = sns_client.post_to_platforms(posts)
    except Exception as e:
        logger.error(f"投稿処理中に予期せぬエラーが発生しました: {e}")
        return jsonify({"success": False, "error": f"投稿処理中にエラーが発生しました: {str(e)}"}), 500

    # 全体の成功・失敗を判定
    all_success = all(result.get("success", False) for result in results.values())

    return jsonify({
        "success": all_success,
        "results": results
    })

@app.route('/api/upload', methods=['POST'])
def upload_media():
    """メディアファイルをアップロードする"""
    if 'files[]' not in request.files:
        return jsonify({"success": False, "error": "ファイルが送信されていません"}), 400

    uploaded_files = request.files.getlist('files[]')
    if not uploaded_files or uploaded_files[0].filename == '':
        return jsonify({"success": False, "error": "ファイルが選択されていません"}), 400

    uploaded_file_paths = []
    media_infos = []

    try:
        for file in uploaded_files:
            if file and allowed_file(file.filename):
                # 安全なファイル名を生成
                filename = secure_filename(file.filename)
                # ユニークなファイル名を作成
                unique_filename = f"{str(uuid.uuid4())}_{filename}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)

                try:
                    # ファイルを保存
                    file.save(file_path)
                    uploaded_file_paths.append(file_path)

                    # メディア情報を作成
                    media_infos.append({
                        "name": filename,
                        "path": file_path,
                        "size": os.path.getsize(file_path),
                        "type": file.content_type
                    })
                except Exception as e:
                    logger.error(f"ファイルの保存中にエラーが発生しました: {e}")
                    return jsonify({"success": False, "error": f"ファイル {filename} の保存中にエラーが発生しました"}), 500
            else:
                logger.warning(f"許可されていないファイル形式: {file.filename if file else 'None'}")
    except Exception as e:
        logger.error(f"ファイルアップロード処理中にエラーが発生しました: {e}")
        return jsonify({"success": False, "error": f"ファイルのアップロード中にエラーが発生しました: {str(e)}"}), 500

    if not uploaded_file_paths:
        return jsonify({"success": False, "error": "ファイルのアップロードに失敗しました"}), 400

    return jsonify({
        "success": True,
        "message": f"{len(uploaded_file_paths)}個のファイルがアップロードされました",
        "files": media_infos
    })

@app.route('/api/post-with-media', methods=['POST'])
def post_with_media():
    """メディア付きで投稿する"""
    data = request.json

    if not data:
        return jsonify({"success": False, "error": "データが送信されていません"}), 400

    posts = {}
    media_files = data.get('media_files', [])

    for platform in ["bluesky", "x", "threads", "misskey", "mastodon"]:
        if platform in data and data[platform]["selected"]:
            posts[platform] = data[platform]["content"]

    if not posts:
        return jsonify({"success": False, "error": "投稿先のSNSが選択されていません"}), 400

    results = {}
    for platform, content in posts.items():
        try:
            result = sns_client.post_with_media_to_platform(platform, content, media_files)
            results[platform] = result
        except Exception as e:
            logger.error(f"プラットフォーム {platform} へのメディア付き投稿でエラー発生: {e}")
            results[platform] = {"success": False, "error": f"投稿処理中にエラーが発生しました: {str(e)}"}

    # 全体の成功・失敗を判定
    all_success = all(result.get("success", False) for result in results.values())

    return jsonify({
        "success": all_success,
        "results": results
    })

@app.route('/api/schedule', methods=['POST'])
def schedule_post():
    """投稿を予約する"""
    data = request.json

    if not data:
        return jsonify({"success": False, "error": "データが送信されていません"}), 400

    scheduled_time = data.get('scheduled_time')
    if not scheduled_time:
        return jsonify({"success": False, "error": "予約時間が指定されていません"}), 400

    # 予約時間のログ出力
    logger.info(f"受信した予約時間: {scheduled_time}")

    # 投稿モードを取得
    post_mode = data.get('post_mode', 'unified')
    logger.info(f"投稿モード: {post_mode}")

    # 投稿コンテンツを取得
    content = ""
    if post_mode == 'unified':
        # 一括モードの場合、共通のコンテンツを使用
        content = data.get('content', "")
        logger.info(f"一括モードのコンテンツ: {content[:50]}...")
    else:
        # 個別モードの場合、プラットフォームごとのコンテンツを辞書として保存
        content = {}
        for platform in ["bluesky", "x", "threads", "misskey", "mastodon"]:
            if platform in data and data[platform].get("selected"):
                content[platform] = data[platform].get("content", "")
                logger.info(f"個別モード: {platform}のコンテンツ: {content[platform][:50]}...")

    # プラットフォーム情報を取得
    platforms = {}
    for platform in ["bluesky", "x", "threads", "misskey", "mastodon"]:
        if platform in data and data[platform].get("selected"):
            # プラットフォーム情報にコンテンツを明示的に含める
            platform_content = data[platform].get("content", "")
            platforms[platform] = {
                "selected": True,
                "content": platform_content
            }
            logger.info(f"{platform}のプラットフォーム情報を設定: コンテンツ長 {len(platform_content)}")

    if not platforms:
        return jsonify({"success": False, "error": "投稿先のSNSが選択されていません"}), 400

    # メディアファイル情報
    media_paths = {"files": data.get('media_files', [])} if 'media_files' in data else None

    # 予約投稿をデータベースに保存
    db = ScheduledPostDB()

    post_id = db.add_scheduled_post(
        content=content,
        platforms=platforms,
        scheduled_time=scheduled_time,
        media_paths=media_paths,
        post_mode=post_mode
    )

    return jsonify({
        "success": True,
        "message": "投稿が予約されました",
        "post_id": post_id,
        "scheduled_time": scheduled_time
    })

@app.route('/api/scheduled-posts', methods=['GET'])
def get_scheduled_posts():
    """予約済み投稿の一覧を取得する"""
    db = ScheduledPostDB()
    posts = db.get_all_scheduled_posts()

    # JSONデータをデコード
    for post in posts:
        if 'platforms' in post:
            try:
                if isinstance(post['platforms'], str):
                    post['platforms'] = json.loads(post['platforms'])
            except:
                logger.error(f"プラットフォーム情報のJSONデコードに失敗: ID={post.get('id')}")

        if 'content' in post:
            try:
                if isinstance(post['content'], str):
                    post['content'] = json.loads(post['content'])
            except:
                pass  # 文字列の場合そのまま

        if 'media_paths' in post and post['media_paths']:
            try:
                if isinstance(post['media_paths'], str):
                    post['media_paths'] = json.loads(post['media_paths'])
            except:
                pass

    return jsonify({
        "success": True,
        "posts": posts
    })

@app.route('/api/delete-scheduled-post/<int:post_id>', methods=['DELETE'])
def delete_scheduled_post(post_id):
    """予約済み投稿を削除する"""
    db = ScheduledPostDB()
    db.delete_scheduled_post(post_id)

    return jsonify({
        "success": True,
        "message": f"投稿ID {post_id} の予約が削除されました"
    })

@app.route('/api/character_limits', methods=['GET'])
def character_limits():
    """各SNSの文字数制限を返す"""
    return jsonify(get_character_limits())

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """アップロードされたファイルを提供する"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# 管理用APIを追加（デバッグ・テスト用）
@app.route('/api/debug/force-check-scheduled', methods=['GET'])
def force_check_scheduled():
    """予約投稿の強制チェックを行う（デバッグ・テスト用）"""
    try:
        logger.info("予約投稿の強制チェックを実行")
        # 現在の時刻以前の予約投稿を取得
        db = ScheduledPostDB()
        pending_posts = db.get_pending_posts()

        # スケジューラーの_scheduler_loop関数の一部を直接実行
        for post in pending_posts:
            logger.info(f"強制処理: 予約投稿ID={post['id']}, 時間={post['scheduled_time']}")

            # 投稿データの準備
            try:
                # JSONデータのデコード
                platforms = json.loads(post['platforms']) if isinstance(post['platforms'], str) else post['platforms']
                content = json.loads(post['content']) if isinstance(post['content'], str) else post['content']

                post_data = {}

                # メディアパスを取得（存在する場合）
                media_paths = json.loads(post['media_paths']) if post['media_paths'] else None

                # プラットフォームごとに投稿データを準備
                for platform, platform_content in platforms.items():
                    if isinstance(platform_content, dict) and platform_content.get('selected'):
                        post_data[platform] = platform_content

                if not post_data:
                    logger.error(f"投稿先のプラットフォームが選択されていません: ID={post['id']}")
                    db.update_post_status(post['id'], 'failed')
                    continue

                # 実際の投稿はスキップして、ステータスのみ更新（テスト用）
                db.update_post_status(post['id'], 'completed')
                logger.info(f"強制処理完了: ID={post['id']}")

            except Exception as e:
                logger.error(f"強制処理エラー: {e}")
                db.update_post_status(post['id'], 'failed')

        return jsonify({
            "success": True,
            "message": f"{len(pending_posts)}件の予約投稿をチェックしました",
            "checked_posts": [post['id'] for post in pending_posts]
        })

    except Exception as e:
        logger.error(f"強制チェックエラー: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# 管理用API: スケジュールされた投稿を現在時刻に設定する（テスト用）
@app.route('/api/debug/set-post-now/<int:post_id>', methods=['POST'])
def set_post_now(post_id):
    """指定された投稿の予約時間を現在時刻に設定する（テスト用）"""
    try:
        logger.info(f"投稿ID {post_id} の予約時間を現在時刻に設定")

        # 現在時刻を取得
        now = datetime.now().isoformat()

        # データベースに接続
        db = ScheduledPostDB()

        # 投稿を取得
        posts = db.get_all_scheduled_posts()
        post = next((p for p in posts if p['id'] == post_id), None)

        if not post:
            return jsonify({
                "success": False,
                "error": f"投稿ID {post_id} が見つかりません"
            }), 404

        # SQLAlchemyを使って直接投稿のscheduled_timeを更新
        conn = engine.connect()
        stmt = update(ScheduledPost).where(ScheduledPost.id == post_id).values(scheduled_time=now)
        conn.execute(stmt)
        conn.commit()
        conn.close()

        return jsonify({
            "success": True,
            "message": f"投稿ID {post_id} の予約時間を {now} に更新しました"
        })

    except Exception as e:
        logger.error(f"投稿時間更新エラー: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500

# 管理用API: 予約投稿を即時に実行する（デバッグ用）
@app.route('/api/debug/execute-scheduled-post/<int:post_id>', methods=['POST'])
def execute_scheduled_post(post_id):
    """指定された予約投稿を即時に実行する（デバッグ用）"""
    try:
        logger.info(f"投稿ID {post_id} の即時実行を開始")

        # データベースに接続
        db = ScheduledPostDB()

        # 投稿を取得
        posts = db.get_all_scheduled_posts()
        post = next((p for p in posts if p['id'] == post_id), None)

        if not post:
            return jsonify({
                "success": False,
                "error": f"投稿ID {post_id} が見つかりません"
            }), 404

        # 投稿データの準備
        try:
            # 詳細なログ出力
            logger.info(f"投稿データ: {post}")

            # JSONデータのデコード
            platforms = json.loads(post['platforms']) if isinstance(post['platforms'], str) else post['platforms']
            content = post['content']
            post_mode = post.get('post_mode', 'unified')

            logger.info(f"投稿モード: {post_mode}")
            logger.info(f"プラットフォーム情報: {platforms}")
            logger.info(f"コンテンツ情報: {content if isinstance(content, str) else 'オブジェクト'}")

            # メディアパスを取得（存在する場合）
            media_paths = None
            if post.get('media_paths'):
                media_paths = json.loads(post['media_paths']) if isinstance(post['media_paths'], str) else post['media_paths']
                logger.info(f"メディア情報: {media_paths}")

            # 投稿するプラットフォームの準備
            post_data = {}
            for platform, platform_content in platforms.items():
                if isinstance(platform_content, dict) and platform_content.get('selected'):
                    post_data[platform] = platform_content
                    logger.info(f"{platform}が選択されています: {platform_content}")

            if not post_data:
                return jsonify({
                    "success": False,
                    "error": "投稿先のプラットフォームが選択されていません"
                }), 400

            # 各プラットフォームへの投稿実行
            results = {}
            success = True

            for platform, platform_data in post_data.items():
                try:
                    # プラットフォームごとのコンテンツ取得
                    platform_content = None

                    # データから直接コンテンツを取得
                    if isinstance(platform_data, dict) and 'content' in platform_data:
                        platform_content = platform_data['content']
                        logger.info(f"プラットフォーム情報から直接コンテンツを取得: {platform} -> {platform_content[:50]}...")
                    # 個別投稿モードの場合
                    elif post_mode == 'individual' and isinstance(content, dict) and platform in content:
                        platform_content = content[platform]
                        logger.info(f"個別モードからコンテンツを取得: {platform} -> {platform_content[:50]}...")
                    # 一括投稿モードの場合
                    elif post_mode == 'unified':
                        if isinstance(content, str):
                            platform_content = content
                        elif isinstance(content, dict) and 'text' in content:
                            platform_content = content['text']
                        else:
                            platform_content = str(content)
                        logger.info(f"一括モードからコンテンツを取得: {platform} -> {platform_content[:50]}...")

                    if not platform_content or not platform_content.strip():
                        error_msg = f"プラットフォーム {platform} のコンテンツが空です"
                        logger.error(error_msg)
                        results[platform] = {"success": False, "error": error_msg}
                        success = False
                        continue

                    # メディア付き投稿または通常投稿
                    if media_paths and media_paths.get('files'):
                        result = sns_client.post_with_media_to_platform(
                            platform,
                            platform_content,
                            media_paths['files']
                        )
                    else:
                        result = sns_client.post_to_platform(platform, platform_content)

                    results[platform] = result

                    if not result.get('success'):
                        logger.error(f"プラットフォーム {platform} への投稿に失敗: {result.get('error')}")
                        success = False
                    else:
                        logger.info(f"プラットフォーム {platform} への投稿に成功")

                except Exception as e:
                    error_msg = f"プラットフォーム {platform} への投稿でエラー発生: {e}"
                    logger.error(error_msg)
                    results[platform] = {"success": False, "error": error_msg}
                    success = False

            # 投稿状態の更新
            final_status = 'completed' if success else 'failed'
            db.update_post_status(post['id'], final_status)
            logger.info(f"投稿ID {post['id']} の状態を {final_status} に更新しました")

            return jsonify({
                "success": success,
                "message": "投稿処理が完了しました",
                "status": final_status,
                "results": results
            })

        except json.JSONDecodeError as e:
            error_msg = f"JSONデコードエラー: {e}"
            logger.error(error_msg)
            db.update_post_status(post['id'], 'failed')
            return jsonify({"success": False, "error": error_msg}), 500
        except Exception as e:
            error_msg = f"投稿処理中の予期せぬエラー: {e}"
            logger.error(error_msg)
            db.update_post_status(post['id'], 'failed')
            return jsonify({"success": False, "error": error_msg}), 500

    except Exception as e:
        error_msg = f"投稿実行エラー: {e}"
        logger.error(error_msg)
        return jsonify({
            "success": False,
            "error": error_msg
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
