// SNS Poster App - Main JavaScript

// APIエンドポイント
const API_URL = {
    PLATFORMS: '/api/platforms',
    CHARACTER_LIMITS: '/api/character_limits',
    POST: '/api/post',
    UPLOAD: '/api/upload',
    POST_WITH_MEDIA: '/api/post-with-media',
    SCHEDULE: '/api/schedule',
    SCHEDULED_POSTS: '/api/scheduled-posts',
    DELETE_SCHEDULED_POST: '/api/delete-scheduled-post'
};

// グローバル変数
let platforms = {}; // 利用可能なプラットフォーム
let characterLimits = {}; // 文字数制限
let postMode = 'unified'; // 投稿モード (unified or individual)
let isDarkMode = false; // ダークモード状態
let uploadedMediaFiles = []; // アップロードされたメディアファイル
let isScheduled = false; // 予約投稿モードか通常投稿モードか

// DOMが読み込まれた後に実行
document.addEventListener('DOMContentLoaded', function() {
    // ダークモードの初期設定
    initDarkMode();

    // 初期化
    initApp();

    // モード切り替えボタンのイベントリスナー
    document.getElementById('unified-mode-btn').addEventListener('click', () => switchMode('unified'));
    document.getElementById('individual-mode-btn').addEventListener('click', () => switchMode('individual'));

    // 投稿ボタンのイベントリスナー
    document.getElementById('post-button').addEventListener('click', handlePost);

    // ダークモード切り替えボタンのイベントリスナー
    document.getElementById('dark-mode-toggle').addEventListener('click', toggleDarkMode);

    // メディアアップロード関連のイベントリスナー設定
    setupMediaUpload();

    // 予約投稿関連のイベントリスナー設定
    setupScheduleToggle();

    // 予約投稿一覧の更新ボタンのイベントリスナー
    document.getElementById('refresh-scheduled-posts').addEventListener('click', fetchScheduledPosts);

    // 初期表示時に予約投稿一覧を取得
    fetchScheduledPosts();
});

// ダークモード初期設定
function initDarkMode() {
    // ローカルストレージからダークモード設定を取得
    const savedMode = localStorage.getItem('darkMode');
    isDarkMode = savedMode === 'true';

    // ダークモードボタンのテキスト更新
    updateDarkModeButtonText();

    // ダークモード適用
    applyDarkMode(isDarkMode);
}

// ダークモードの切り替え
function toggleDarkMode() {
    isDarkMode = !isDarkMode;

    // ローカルストレージに設定を保存
    localStorage.setItem('darkMode', isDarkMode);

    // ダークモードボタンのテキスト更新
    updateDarkModeButtonText();

    // ダークモード適用
    applyDarkMode(isDarkMode);
}

// ダークモードボタンのテキスト更新
function updateDarkModeButtonText() {
    const button = document.getElementById('dark-mode-toggle');
    button.textContent = isDarkMode ? 'ライトモードへ切替' : 'ダークモードへ切替';
}

// ダークモードの適用
function applyDarkMode(enable) {
    const lightStylesheet = document.querySelector('link[title="light"]');
    const darkStylesheet = document.querySelector('link[title="dark"]');

    if (enable) {
        lightStylesheet.disabled = true;
        darkStylesheet.disabled = false;
    } else {
        lightStylesheet.disabled = false;
        darkStylesheet.disabled = true;
    }
}

// アプリ初期化
async function initApp() {
    try {
        // 利用可能なプラットフォームを取得
        platforms = await fetchPlatforms();

        // 文字数制限を取得
        characterLimits = await fetchCharacterLimits();

        // プラットフォーム選択UIを生成
        renderPlatformSelectors();

        // 一括投稿モードの文字数カウント設定
        setupUnifiedModeCounters();

        // 初期状態は一括投稿モード
        switchMode('unified');
    } catch (error) {
        showError('アプリの初期化中にエラーが発生しました: ' + error.message);
    }
}

// プラットフォーム情報を取得
async function fetchPlatforms() {
    const response = await fetch(API_URL.PLATFORMS);
    if (!response.ok) {
        throw new Error(`プラットフォーム情報の取得に失敗しました: ${response.status}`);
    }
    return await response.json();
}

// 文字数制限を取得
async function fetchCharacterLimits() {
    const response = await fetch(API_URL.CHARACTER_LIMITS);
    if (!response.ok) {
        throw new Error(`文字数制限の取得に失敗しました: ${response.status}`);
    }
    return await response.json();
}

// プラットフォーム選択UIの生成
function renderPlatformSelectors() {
    const container = document.getElementById('platforms-container');
    container.innerHTML = '';

    Object.keys(platforms).forEach(platform => {
        const platformInfo = platforms[platform];
        const card = document.createElement('div');
        card.className = `platform-card ${platformInfo.enabled ? 'enabled' : 'disabled'}`;
        card.dataset.platform = platform;

        if (platformInfo.enabled) {
            card.addEventListener('click', () => togglePlatformSelection(card));
        }

        // プラットフォーム名（先頭を大文字に）
        const displayName = platform.charAt(0).toUpperCase() + platform.slice(1);

        card.innerHTML = `
            <div class="platform-name">${displayName}</div>
            <div class="platform-status">${platformInfo.enabled ? '連携済み' : '未連携'}</div>
            <div class="platform-limit">最大 ${platformInfo.limit} 文字</div>
        `;

        container.appendChild(card);
    });
}

// プラットフォーム選択の切り替え
function togglePlatformSelection(card) {
    // 無効化されたプラットフォームは選択不可
    if (card.classList.contains('disabled')) {
        return;
    }

    // 選択/非選択を切り替え
    card.classList.toggle('selected');

    // 選択状態に基づいて個別投稿モードのUIを更新
    updateIndividualPosts();
}

// 一括投稿モードの文字数カウンター設定
function setupUnifiedModeCounters() {
    const textarea = document.getElementById('unified-content');
    const counter = document.getElementById('unified-character-count');

    // 最も小さい文字数制限を見つける
    const minLimit = Math.min(...Object.values(characterLimits));
    textarea.setAttribute('maxlength', minLimit);

    // テキスト入力時のカウント更新
    textarea.addEventListener('input', function() {
        const length = this.value.length;
        counter.textContent = `${length} / ${minLimit}`;

        // 文字数が多い場合は警告表示
        if (length > minLimit * 0.9) {
            counter.style.color = isDarkMode ? '#f87171' : '#e74c3c';
        } else {
            counter.style.color = isDarkMode ? '#aaa' : '#666';
        }
    });
}

// 個別投稿モードのUI更新
function updateIndividualPosts() {
    const container = document.getElementById('individual-posts-container');
    container.innerHTML = '';

    // 選択されたプラットフォームのみ表示
    const selectedPlatforms = Array.from(document.querySelectorAll('.platform-card.selected'))
        .map(card => card.dataset.platform);

    if (selectedPlatforms.length === 0) {
        container.innerHTML = '<p>投稿先のSNSを選択してください</p>';
        return;
    }

    // 統一モードのテキストを取得（あれば）
    const unifiedText = document.getElementById('unified-content').value;

    selectedPlatforms.forEach(platform => {
        const limit = characterLimits[platform];
        const displayName = platform.charAt(0).toUpperCase() + platform.slice(1);

        const postDiv = document.createElement('div');
        postDiv.className = 'individual-post';
        postDiv.dataset.platform = platform;

        postDiv.innerHTML = `
            <div class="individual-post-header">
                <div class="individual-post-platform">${displayName}</div>
                <div class="platform-limit">最大 ${limit} 文字</div>
            </div>
            <div class="textarea-container">
                <textarea class="individual-content" data-platform="${platform}" placeholder="${displayName}に投稿する内容を入力..." maxlength="${limit}">${unifiedText}</textarea>
                <div class="character-count">${unifiedText.length} / ${limit}</div>
            </div>
        `;

        container.appendChild(postDiv);
    });

    // 個別の文字数カウンター設定
    setupIndividualCounters();
}

// 個別投稿モードの文字数カウンター設定
function setupIndividualCounters() {
    const textareas = document.querySelectorAll('.individual-content');

    textareas.forEach(textarea => {
        const platform = textarea.dataset.platform;
        const limit = characterLimits[platform];
        const counter = textarea.parentElement.querySelector('.character-count');

        textarea.addEventListener('input', function() {
            const length = this.value.length;
            counter.textContent = `${length} / ${limit}`;

            // 文字数が多い場合は警告表示
            if (length > limit * 0.9) {
                counter.style.color = isDarkMode ? '#f87171' : '#e74c3c';
            } else {
                counter.style.color = isDarkMode ? '#aaa' : '#666';
            }
        });
    });
}

// モード切り替え
function switchMode(mode) {
    postMode = mode;

    // モード切り替えボタンのスタイル更新
    document.getElementById('unified-mode-btn').classList.toggle('active', mode === 'unified');
    document.getElementById('individual-mode-btn').classList.toggle('active', mode === 'individual');

    // モードに応じたUIの表示/非表示
    document.getElementById('unified-mode').style.display = mode === 'unified' ? 'block' : 'none';
    document.getElementById('individual-mode').style.display = mode === 'individual' ? 'block' : 'none';

    // 個別モードの場合、選択されたプラットフォームのUIを更新
    if (mode === 'individual') {
        updateIndividualPosts();
    }
}

// メディアアップロード関連の設定
function setupMediaUpload() {
    const dropzone = document.getElementById('media-dropzone');
    const mediaInput = document.getElementById('media-input');
    const preview = document.getElementById('media-preview');

    // クリックでファイル選択
    dropzone.addEventListener('click', () => mediaInput.click());

    // ドラッグ＆ドロップイベントリスナー
    dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropzone.classList.add('dragover');
    });

    dropzone.addEventListener('dragleave', (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropzone.classList.remove('dragover');
    });

    dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropzone.classList.remove('dragover');

        if (e.dataTransfer.files.length > 0) {
            handleFiles(e.dataTransfer.files);
        }
    });

    // ファイル入力の変更イベント
    mediaInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFiles(e.target.files);
        }
    });
}

// ファイル処理
async function handleFiles(files) {
    // ファイル数の検証（最大4枚まで）
    if (uploadedMediaFiles.length + files.length > 4) {
        showError('アップロードできるメディアは最大4つまでです');
        return;
    }

    const preview = document.getElementById('media-preview');

    // FormDataの準備
    const formData = new FormData();

    // ファイルをFormDataに追加
    for (let i = 0; i < files.length; i++) {
        const file = files[i];
        formData.append('files[]', file);

        // ファイルタイプをチェック（画像か動画のみ許可）
        if (!file.type.match('image.*') && !file.type.match('video.*')) {
            showError('画像または動画ファイルのみアップロードできます');
            return;
        }
    }

    try {
        // アップロード中の表示
        const loadingDiv = document.createElement('div');
        loadingDiv.className = 'media-loading';
        loadingDiv.innerHTML = '<p>アップロード中...</p>';
        preview.appendChild(loadingDiv);

        // APIにアップロード
        const response = await fetch(API_URL.UPLOAD, {
            method: 'POST',
            body: formData
        });

        // アップロード中の表示を削除
        loadingDiv.remove();

        if (!response.ok) {
            throw new Error('アップロードに失敗しました');
        }

        const result = await response.json();

        if (!result.success) {
            throw new Error(result.error || 'アップロードに失敗しました');
        }

        // アップロードされたファイル情報を保存
        uploadedMediaFiles = uploadedMediaFiles.concat(result.files);

        // プレビュー表示を更新
        updateMediaPreview();

    } catch (error) {
        showError('ファイルのアップロードに失敗しました: ' + error.message);
    }
}

// メディアプレビューの更新
function updateMediaPreview() {
    const preview = document.getElementById('media-preview');
    preview.innerHTML = '';

    if (uploadedMediaFiles.length === 0) {
        return;
    }

    uploadedMediaFiles.forEach((file, index) => {
        const mediaItem = document.createElement('div');
        mediaItem.className = 'media-item';

        // 画像か動画かによって表示を分ける
        if (file.type.startsWith('image/')) {
            mediaItem.innerHTML = `
                <img src="/uploads/${file.path.split('/').pop()}" alt="${file.name}">
                <button class="remove-media" data-index="${index}">×</button>
            `;
        } else if (file.type.startsWith('video/')) {
            mediaItem.innerHTML = `
                <video controls>
                    <source src="/uploads/${file.path.split('/').pop()}" type="${file.type}">
                </video>
                <button class="remove-media" data-index="${index}">×</button>
            `;
        }

        preview.appendChild(mediaItem);
    });

    // 削除ボタンのイベントリスナー
    document.querySelectorAll('.remove-media').forEach(button => {
        button.addEventListener('click', function() {
            const index = parseInt(this.dataset.index);
            uploadedMediaFiles.splice(index, 1);
            updateMediaPreview();
        });
    });
}

// 予約投稿トグルのセットアップ
function setupScheduleToggle() {
    const scheduleToggle = document.getElementById('schedule-toggle');
    const scheduleOptions = document.getElementById('schedule-options');
    const scheduledTimeInput = document.getElementById('scheduled-time');

    // 現在の日時を取得して、日時入力の最小値を設定
    const now = new Date();
    const timezoneOffset = now.getTimezoneOffset() * 60000;
    const localISOTime = (new Date(now - timezoneOffset)).toISOString().slice(0, 16);
    scheduledTimeInput.min = localISOTime;

    // トグルでオプション表示/非表示を切り替え
    scheduleToggle.addEventListener('change', function() {
        scheduleOptions.classList.toggle('hidden', !this.checked);
        isScheduled = this.checked;
    });
}

// 予約投稿一覧の取得と表示
async function fetchScheduledPosts() {
    try {
        const container = document.getElementById('scheduled-posts-container');
        container.innerHTML = '<p class="loading">読み込み中...</p>';

        const response = await fetch(API_URL.SCHEDULED_POSTS);
        if (!response.ok) {
            throw new Error('予約投稿の取得に失敗しました');
        }

        const result = await response.json();

        // 予約投稿一覧を表示
        renderScheduledPosts(result.posts);

    } catch (error) {
        document.getElementById('scheduled-posts-container').innerHTML =
            `<p class="error">エラー: ${error.message}</p>`;
    }
}

// 予約投稿一覧の表示
function renderScheduledPosts(posts) {
    const container = document.getElementById('scheduled-posts-container');
    container.innerHTML = '';

    console.log('受け取った予約投稿:', posts); // デバッグ用ログ

    if (!posts || posts.length === 0) {
        container.innerHTML = '<p class="no-scheduled-posts">予約済みの投稿はありません</p>';
        return;
    }

    posts.forEach(post => {
        console.log('各投稿データ:', post); // 各投稿情報のデバッグ

        // プラットフォーム情報の取得と品質チェック
        let platforms = {};
        try {
            if (typeof post.platforms === 'string') {
                platforms = JSON.parse(post.platforms);
            } else if (typeof post.platforms === 'object') {
                platforms = post.platforms;
            }
            console.log('パースしたプラットフォーム情報:', platforms);
        } catch (e) {
            console.error('プラットフォーム情報の解析に失敗:', e);
            platforms = {};
        }

        // プラットフォーム名を取得
        const platformNames = Object.keys(platforms)
            .filter(p => platforms[p] && platforms[p].selected)
            .map(p => p.charAt(0).toUpperCase() + p.slice(1))
            .join(', ');

        console.log('表示するプラットフォーム名:', platformNames);

        // 日時のフォーマット
        const scheduledDate = new Date(post.scheduled_time);
        const formattedDate = `${scheduledDate.getFullYear()}/${(scheduledDate.getMonth() + 1).toString().padStart(2, '0')}/${scheduledDate.getDate().toString().padStart(2, '0')} ${scheduledDate.getHours().toString().padStart(2, '0')}:${scheduledDate.getMinutes().toString().padStart(2, '0')}`;

        // 投稿内容のテキスト処理
        let contentText = '';
        try {
            // 全てのプラットフォームが同じ内容の場合は最初のプラットフォームの内容を表示
            if (typeof post.content === 'string') {
                try {
                    const contentObj = JSON.parse(post.content);
                    // JSONとしてパースできる場合はその最初のプラットフォームの内容を表示
                    if (typeof contentObj === 'object') {
                        contentText = Object.values(contentObj)[0] || '';
                    } else {
                        contentText = contentObj;
                    }
                } catch {
                    // JSONとしてパースできない場合はそのまま文字列として表示
                    contentText = post.content;
                }
            } else if (typeof post.content === 'object') {
                // オブジェクトの場合は最初のプラットフォームの内容を表示
                contentText = Object.values(post.content)[0] || '';
            }

            // もしcontentがプラットフォームごとに分かれている場合、最初のプラットフォームの内容を表示
            if (!contentText && platforms) {
                const firstPlatform = Object.keys(platforms)[0];
                if (firstPlatform && platforms[firstPlatform] && platforms[firstPlatform].content) {
                    contentText = platforms[firstPlatform].content;
                }
            }

            console.log('表示するコンテンツ:', contentText);
        } catch (e) {
            console.error('コンテンツの解析エラー:', e);
            contentText = '内容の読み込みエラー';
        }

        // 投稿ステータスに応じたクラス
        const statusClass = post.status === 'completed' ? 'completed' :
                           post.status === 'failed' ? 'failed' : 'pending';

        // 投稿ステータスの日本語表示
        const statusText = post.status === 'completed' ? '完了' :
                          post.status === 'failed' ? '失敗' : '待機中';

        // メディア情報（あれば）
        const hasMedia = post.media_paths && post.media_paths.files && post.media_paths.files.length > 0;

        const postItem = document.createElement('div');
        postItem.className = `scheduled-post-item ${statusClass}`;
        postItem.innerHTML = `
            <div class="scheduled-post-header">
                <div class="scheduled-time">${formattedDate}</div>
                <div class="scheduled-status ${statusClass}">${statusText}</div>
            </div>
            <div class="scheduled-post-content">
                <div class="scheduled-platforms">投稿先: ${platformNames}</div>
                <div class="scheduled-text">${contentText.length > 100 ? contentText.slice(0, 100) + '...' : contentText}</div>
                ${hasMedia ? '<div class="scheduled-media-info">メディア: あり</div>' : ''}
            </div>
            <div class="scheduled-post-actions">
                <button class="delete-scheduled-post" data-id="${post.id}">削除</button>
            </div>
        `;

        container.appendChild(postItem);
    });

    // 削除ボタンのイベントリスナーを設定
    document.querySelectorAll('.delete-scheduled-post').forEach(button => {
        button.addEventListener('click', async function() {
            if (confirm('この予約投稿を削除してもよろしいですか？')) {
                const postId = this.dataset.id;
                await deleteScheduledPost(postId);
                fetchScheduledPosts(); // 一覧を更新
            }
        });
    });
}

// 予約投稿の削除
async function deleteScheduledPost(postId) {
    try {
        const response = await fetch(`${API_URL.DELETE_SCHEDULED_POST}/${postId}`, {
            method: 'DELETE'
        });

        if (!response.ok) {
            throw new Error('予約投稿の削除に失敗しました');
        }

        showSuccess('予約投稿を削除しました');

    } catch (error) {
        showError('予約投稿の削除に失敗しました: ' + error.message);
    }
}

// 投稿処理
async function handlePost() {
    try {
        // 選択されたプラットフォームを取得
        const selectedPlatforms = Array.from(document.querySelectorAll('.platform-card.selected'))
            .map(card => card.dataset.platform);

        if (selectedPlatforms.length === 0) {
            showError('投稿先のSNSを選択してください');
            return;
        }

        // 投稿データの準備
        const postData = {
            post_mode: postMode
        };

        // 一括モードの場合
        if (postMode === 'unified') {
            const unifiedContent = document.getElementById('unified-content').value;
            if (!unifiedContent.trim()) {
                showError('投稿内容が空です');
                return;
            }
            postData.content = unifiedContent;
        }

        // プラットフォームごとのデータを設定
        selectedPlatforms.forEach(platform => {
            let content = '';

            if (postMode === 'unified') {
                // 一括モードの場合、共通のテキストを使用
                content = document.getElementById('unified-content').value;
            } else {
                // 個別モードの場合、プラットフォームごとのテキストを使用
                const textarea = document.querySelector(`.individual-content[data-platform="${platform}"]`);
                content = textarea ? textarea.value : '';
            }

            if (!content.trim()) {
                showError(`${platform}の投稿内容が空です`);
                return;
            }

            postData[platform] = {
                selected: true,
                content: content
            };
        });

        // メディアファイルがある場合は追加
        if (uploadedMediaFiles.length > 0) {
            postData.media_files = uploadedMediaFiles.map(file => file.path);
        }

        // 予約投稿の場合
        if (isScheduled) {
            const scheduledTime = document.getElementById('scheduled-time').value;
            if (!scheduledTime) {
                showError('予約時間を指定してください');
                return;
            }

            postData.scheduled_time = scheduledTime;
            const response = await fetch(API_URL.SCHEDULE, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(postData)
            });

            if (!response.ok) {
                throw new Error('予約投稿に失敗しました');
            }

            const result = await response.json();
            showSuccess('投稿が予約されました');
            fetchScheduledPosts();  // 予約投稿一覧を更新
        } else {
            // 即時投稿の場合
            const endpoint = uploadedMediaFiles.length > 0 ? API_URL.POST_WITH_MEDIA : API_URL.POST;
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(postData)
            });

            if (!response.ok) {
                throw new Error('投稿に失敗しました');
            }

            const result = await response.json();
            showPostResults(result.results);
        }

        // フォームをリセット
        resetForm();
    } catch (error) {
        showError(error.message);
    }
}

// 投稿結果の表示
function showPostResults(results) {
    const statusContainer = document.getElementById('status-container');
    statusContainer.innerHTML = '';
    statusContainer.classList.remove('hidden');

    // 結果のヘッダー
    const header = document.createElement('div');
    header.className = 'status-header';
    header.innerHTML = '<h3>投稿結果</h3>';
    statusContainer.appendChild(header);

    // 各プラットフォームの結果をリスト表示
    const resultList = document.createElement('ul');
    resultList.className = 'status-list';

    Object.keys(results).forEach(platform => {
        const result = results[platform];
        const success = result.success;

        const displayName = platform.charAt(0).toUpperCase() + platform.slice(1);

        const listItem = document.createElement('li');
        listItem.className = `status-item ${success ? 'success' : 'error'}`;
        listItem.innerHTML = `
            <div class="status-platform">${displayName}</div>
            <div class="status-message">${success ? '投稿成功' : `エラー: ${result.error || '不明なエラー'}`}</div>
        `;

        resultList.appendChild(listItem);
    });

    statusContainer.appendChild(resultList);

    // 5秒後に結果表示を閉じる
    setTimeout(() => {
        statusContainer.classList.add('hidden');
    }, 5000);

    // すべて成功なら成功メッセージも表示
    const allSuccess = Object.values(results).every(result => result.success);
    if (allSuccess) {
        showSuccess('すべてのプラットフォームへの投稿が完了しました');
    }
}

// フォームのリセット
function resetForm() {
    if (postMode === 'unified') {
        document.getElementById('unified-content').value = '';
        document.getElementById('unified-character-count').textContent = '0 / ' +
            Math.min(...Object.values(characterLimits));
    } else {
        const textareas = document.querySelectorAll('.individual-content');
        textareas.forEach(textarea => {
            const platform = textarea.dataset.platform;
            textarea.value = '';
            textarea.parentElement.querySelector('.character-count').textContent =
                `0 / ${characterLimits[platform]}`;
        });
    }

    // メディアもクリア
    uploadedMediaFiles = [];
    updateMediaPreview();

    // 予約設定もリセット
    document.getElementById('schedule-toggle').checked = false;
    document.getElementById('schedule-options').classList.add('hidden');
    isScheduled = false;
}

// 成功メッセージの表示
function showSuccess(message) {
// ステータスコンテナを利用
const statusContainer = document.getElementById('status-container');
statusContainer.innerHTML = '';
statusContainer.classList.remove('hidden');

// 成功メッセージ用のスタイル
statusContainer.className = 'status-container success-message';

// 結果メッセージ
const messageDiv = document.createElement('div');
messageDiv.className = 'status-message';
messageDiv.innerHTML = `<p>${message}</p>`;
statusContainer.appendChild(messageDiv);

// 5秒後に消去
    setTimeout(() => {
        statusContainer.classList.add('fade-out');
        setTimeout(() => {
            statusContainer.classList.add('hidden');
            statusContainer.classList.remove('fade-out');
        }, 300);
    }, 5000);
}

// エラーメッセージの表示
function showError(message) {
// ステータスコンテナを利用
const statusContainer = document.getElementById('status-container');
statusContainer.innerHTML = '';
statusContainer.classList.remove('hidden');

// エラーメッセージ用のスタイル
statusContainer.className = 'status-container error-message';

// 結果メッセージ
const messageDiv = document.createElement('div');
messageDiv.className = 'status-message';
messageDiv.innerHTML = `<p>エラー: ${message}</p>`;
statusContainer.appendChild(messageDiv);

// 5秒後に消去
    setTimeout(() => {
        statusContainer.classList.add('fade-out');
        setTimeout(() => {
            statusContainer.classList.add('hidden');
            statusContainer.classList.remove('fade-out');
        }, 300);
    }, 5000);
}