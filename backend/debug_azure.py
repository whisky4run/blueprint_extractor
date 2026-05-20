"""
Azure OpenAI 接続確認スクリプト
コンテナ内で実行: python debug_azure.py
"""
import os
import sys

from dotenv import load_dotenv
load_dotenv()

endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
api_key  = os.environ.get("AZURE_OPENAI_API_KEY", "")
deploy   = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
version  = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-01")

print(f"ENDPOINT   : {endpoint}")
print(f"DEPLOYMENT : {deploy}")
print(f"API_VERSION: {version}")
print(f"API_KEY    : {'(set)' if api_key else '(empty!)'}")
print()

if not endpoint or not api_key:
    print("[ERROR] ENDPOINT または API_KEY が未設定です")
    sys.exit(1)

from openai import AzureOpenAI

client = AzureOpenAI(
    azure_endpoint=endpoint,
    api_key=api_key,
    api_version=version,
)

print("--- デプロイ一覧を取得中 ---")
try:
    # モデル一覧はデプロイ名の確認に使える
    models = client.models.list()
    print("利用可能なデプロイ/モデル:")
    for m in models.data:
        print(f"  {m.id}")
except Exception as e:
    print(f"[WARN] モデル一覧取得失敗: {e}")

print()
print(f"--- デプロイ '{deploy}' にテストメッセージを送信中 ---")
try:
    resp = client.chat.completions.create(
        model=deploy,
        messages=[{"role": "user", "content": "Hello"}],
        max_tokens=10,
    )
    print(f"[OK] レスポンス: {resp.choices[0].message.content!r}")
except Exception as e:
    print(f"[ERROR] {e}")
    print()
    print("確認ポイント:")
    print("  1. AZURE_OPENAI_DEPLOYMENT がAzureポータルの「デプロイ名」と一致しているか")
    print("  2. AZURE_OPENAI_ENDPOINT の形式: https://<resource>.openai.azure.com/")
    print("  3. AZURE_OPENAI_API_VERSION: 2024-02-01 または 2024-05-01-preview など")
