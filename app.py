import streamlit as st
import json
import urllib.request
import urllib.parse
import uuid
import websocket # pip install websocket-client
from PIL import Image
import io
import random
import os
from dotenv import load_dotenv
load_dotenv()

# ==========================================
# 設定
# ==========================================
SERVER_ADDRESS = os.getenv("COMFY_SERVER_ADDRESS")
CLIENT_ID = str(uuid.uuid4())
JSON_FILE = os.getenv("COMFY_WORKFLOW_PATH")

# ==========================================
# 通信系関数 (ComfyUIとのやり取り)
# ==========================================
def queue_prompt(prompt_workflow):
    p = {"prompt": prompt_workflow, "client_id": CLIENT_ID}
    data = json.dumps(p).encode('utf-8')
    req = urllib.request.Request(f"http://{SERVER_ADDRESS}/prompt", data=data)
    return json.loads(urllib.request.urlopen(req).read())

def get_image(filename, subfolder, folder_type):
    data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    url_values = urllib.parse.urlencode(data)
    with urllib.request.urlopen(f"http://{SERVER_ADDRESS}/view?{url_values}") as response:
        return response.read()

def get_history(prompt_id):
    with urllib.request.urlopen(f"http://{SERVER_ADDRESS}/history/{prompt_id}") as response:
        return json.loads(response.read())

def generate_image_via_ws(prompt_text, workflow_data):
    # WebSocket接続
    ws = websocket.WebSocket()
    ws.connect(f"ws://{SERVER_ADDRESS}/ws?clientId={CLIENT_ID}")
    
    # 1. プロンプトとSeedの書き換え
    # (JSONのIDは環境に合わせて調整してください。前回のIDを使用しています)
    workflow_data["6"]["inputs"]["text"] = prompt_text
    workflow_data["15"]["inputs"]["text"] = prompt_text # Refiner用
    workflow_data["10"]["inputs"]["noise_seed"] = random.randint(1, 10**14)

    # 2. 生成開始
    prompt_id = queue_prompt(workflow_data)['prompt_id']
    
    # 3. 完了待機
    output_images = []
    while True:
        out = ws.recv()
        if isinstance(out, str):
            message = json.loads(out)
            if message['type'] == 'executing':
                data = message['data']
                if data['node'] is None and data['prompt_id'] == prompt_id:
                    break # 生成完了！
        else:
            continue

    # 4. 画像データの取得
    history = get_history(prompt_id)[prompt_id]
    for o in history['outputs']:
        for node_id in history['outputs']:
            node_output = history['outputs'][node_id]
            if 'images' in node_output:
                for image in node_output['images']:
                    image_data = get_image(image['filename'], image['subfolder'], image['type'])
                    output_images.append(image_data)
    
    ws.close()
    return output_images

# ==========================================
# アプリ画面 (Streamlit)
# ==========================================
st.title("🎨 My AI Image Generator")

# JSON読み込み
try:
    with open(JSON_FILE, "r", encoding="utf-8") as f:
        workflow_data = json.load(f)
except FileNotFoundError:
    st.error(f"エラー: {JSON_FILE} が見つかりません。")
    st.stop()

# 入力エリア
user_prompt = st.text_area("プロンプトを入力", value="1girl, masterpiece, best quality, silver hair, looking at viewer", height=100)

# 生成ボタン
if st.button("画像を生成する (Generate)"):
    if not user_prompt:
        st.warning("プロンプトを入力してください")
    else:
        status_text = st.empty()
        status_text.text("⏳ 生成中... ComfyUIが頑張っています...")
        
        try:
            # 生成実行
            images = generate_image_via_ws(user_prompt, workflow_data)
            
            # 画像表示
            status_text.text("✅ 生成完了！")
            for img_data in images:
                image = Image.open(io.BytesIO(img_data))
                st.image(image, caption="Generated Image", use_column_width=True)
                
        except Exception as e:
            st.error(f"エラーが発生しました: {e}")
            status_text.text("❌ エラー")