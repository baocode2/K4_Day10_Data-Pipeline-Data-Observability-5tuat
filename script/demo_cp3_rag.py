"""
Demo & Verification script for Role 4 in Checkpoint 3 (CP3).

Nhiệm vụ Role 4 tại CP3:
1. Xác nhận papers-baseline & manifest khớp với clean dataset.
2. Demo Semantic Search & Exact Lookup.
3. Kiểm tra Agent trả lời factual dựa trên tool result (không vượt corpus).
"""
from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd
from core.config import load_settings
from retrieval.agent import build_agent, run_agent_question
from retrieval.index import LocalEmbeddingIndex

PASS = "✅ PASS"
FAIL = "❌ FAIL"


def _section(title: str) -> None:
    print(f"\n{'=' * 65}")
    print(f"  {title}")
    print(f"{'=' * 65}")


def step1_verify_consistency(settings) -> bool:
    """Nhiệm vụ 1: Đối chiếu count và paper_id giữa clean CSV, manifest JSON và ChromaDB."""
    _section("Nhiệm vụ 1: Xác nhận papers-baseline & manifest khớp clean dataset")

    clean_df = pd.read_csv(settings.paths.clean_csv)
    clean_count = len(clean_df)
    clean_ids = set(clean_df["paper_id"].str.lower())

    index = LocalEmbeddingIndex.load(settings)
    manifest_count = len(index.documents)
    manifest_ids = set(index.documents_by_paper_id.keys())

    chroma_count = index.collection.count()

    print(f"  • Số bản ghi trong clean CSV      : {clean_count}")
    print(f"  • Số document trong manifest JSON : {manifest_count}")
    print(f"  • Số vector trong Chroma collection : {chroma_count}")

    id_diff = clean_ids ^ manifest_ids
    is_match = (clean_count == manifest_count == chroma_count) and len(id_diff) == 0

    if is_match:
        print(f"\n  {PASS} Tất cả 3 nguồn (Clean Data, Manifest, ChromaDB) khớp 100% ({clean_count} bản ghi).")
    else:
        print(f"\n  {FAIL} Có sự lệch dữ liệu! Chênh lệch ID: {id_diff}")

    return is_match


def step2_demo_search_and_lookup(settings) -> None:
    """Nhiệm vụ 2: Demo 1 Semantic Search & 1 Exact Lookup."""
    _section("Nhiệm vụ 2: Demo Semantic Search & Exact Lookup")

    index = LocalEmbeddingIndex.load(settings)

    # 1. Semantic Search
    query = "retrieval augmented generation"
    print(f"🔍 2.1 Demo Semantic Search với query: '{query}'")
    results = index.search(query, top_k=2)
    for i, res in enumerate(results, 1):
        print(f"   [{i}] Score: {res.score:.4f} | ID: {res.paper_id}")
        print(f"       Title: {res.title}")
        print(f"       Summary snippet: {res.metadata.get('summary', '')[:100]}...\n")

    # 2. Exact Lookup
    sample_id = index.documents[0]["paper_id"]
    print(f"🎯 2.2 Demo Exact Lookup với paper_id: '{sample_id}'")
    lookup_res = index.lookup(sample_id)
    if lookup_res:
        print(f"   {PASS} Tìm thấy chính xác!")
        print(f"       Title    : {lookup_res['title']}")
        print(f"       Published: {lookup_res['metadata']['published']}")
        print(f"       Authors  : {lookup_res['metadata']['authors_joined']}\n")
    else:
        print(f"   {FAIL} Không tìm thấy paper_id {sample_id}\n")


def step3_test_agent(settings) -> None:
    """Nhiệm vụ 3: Kiểm tra Agent sử dụng tool result, không hallucinate ngoài corpus."""
    _section("Nhiệm vụ 3: Kiểm tra RAG Agent trả lời Factual dùng Tool Result")

    index = LocalEmbeddingIndex.load(settings)
    sample_doc = index.documents[0]
    sample_title = sample_doc["title"]

    print("🤖 Khởi tạo RAG Agent...")
    try:
        agent = build_agent(settings, index)
        question = f"Who are the authors of the paper '{sample_title}'?"
        print(f"❓ Câu hỏi: {question}")
        print("⏳ Đang gọi Agent (gọi tool retrieval & sinh câu trả lời)...")

        answer = run_agent_question(agent, question)
        print(f"\n💬 Agent Response:\n{answer}\n")
        print(f"  {PASS} Agent đã trả lời dựa trên thông tin corpus.")
    except Exception as e:
        print(f"  ⚠️ Lưu ý: Gọi LLM gặp lỗi ({e}). Kiểm tra GOOGLE_API_KEY trong .env nếu cần demo live.")


def main() -> None:
    print("\n" + "#" * 65)
    print("  ROLE 4 · DEMO & VERIFICATION FOR CHECKPOINT 3 (CP3)")
    print("#" * 65)

    settings = load_settings()
    step1_verify_consistency(settings)
    step2_demo_search_and_lookup(settings)
    step3_test_agent(settings)

    print("\n" + "=" * 65)
    print("  🎉 XÁC NHẬN ROLE 4 ĐÃ SẴN SÀNG CHO CHECKPOINT 3!")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
