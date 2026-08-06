"""
Role 4 — Smoke Test RAG (chạy tại CP2 sau khi build papers-baseline).

Chạy:
    uv run python script/smoke_test_rag_cp2.py

Yêu cầu:
    - data/embeddings/papers_embeddings.json tồn tại (build xong ở CP2)
    - .env đã cấu hình đúng LLM_PROVIDER và API key tương ứng
"""
from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Đảm bảo src/ nằm trong sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.config import load_settings
from retrieval.index import LocalEmbeddingIndex
from retrieval.qa import answer_question

PASS = "✅ PASS"
FAIL = "❌ FAIL"


def _banner(title: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")


def test_manifest_exists(settings) -> bool:
    """Test 0: manifest file tồn tại."""
    _banner("Test 0 — Manifest tồn tại")
    path = settings.paths.embeddings_json
    ok = path.exists()
    print(f"  Path: {path}")
    print(f"  {PASS if ok else FAIL} — {'Found' if ok else 'NOT FOUND — chạy phase1 trước'}")
    return ok


def test_semantic_search(index: LocalEmbeddingIndex) -> bool:
    """Test 1: semantic search trả đúng cấu trúc SearchResult."""
    _banner("Test 1 — Semantic Search")
    query = "retrieval augmented generation large language model"
    results = index.search(query, top_k=3)
    ok = (
        len(results) >= 1
        and all(r.paper_id and r.title and r.content for r in results)
        and all(0.0 <= r.score <= 1.0 for r in results)
    )
    print(f"  Query  : {query!r}")
    print(f"  Hits   : {len(results)}")
    for r in results[:2]:
        print(f"    [{r.score:.4f}] {r.paper_id} — {r.title[:60]}")
    print(f"  {PASS if ok else FAIL}")
    return ok


def test_exact_lookup_id(index: LocalEmbeddingIndex) -> bool:
    """Test 2a: exact lookup theo paper_id trả đúng document."""
    _banner("Test 2a — Exact Lookup by paper_id")
    if not index.documents:
        print(f"  {FAIL} — Không có document trong index")
        return False
    first_doc = index.documents[0]
    paper_id = first_doc["paper_id"]
    result = index.lookup(paper_id)
    ok = result is not None and result["paper_id"].lower() == paper_id.lower()
    print(f"  Lookup paper_id: {paper_id!r}")
    print(f"  Found  : {result['title'][:60] if result else 'None'}")
    print(f"  {PASS if ok else FAIL}")
    return ok


def test_exact_lookup_title(index: LocalEmbeddingIndex) -> bool:
    """Test 2b: exact lookup theo title ra cùng document với lookup by paper_id."""
    _banner("Test 2b — Exact Lookup by title")
    if not index.documents:
        print(f"  {FAIL} — Không có document trong index")
        return False
    first_doc = index.documents[0]
    title = first_doc["title"]
    paper_id = first_doc["paper_id"]
    result = index.lookup(title)
    ok = result is not None and result["paper_id"].lower() == paper_id.lower()
    print(f"  Lookup title : {title[:60]!r}")
    print(f"  paper_id match: {ok}")
    print(f"  {PASS if ok else FAIL}")
    return ok


def test_answer_question(index: LocalEmbeddingIndex, settings) -> bool:
    """Test 3: answer_question trả lời từ metadata, không trả rỗng."""
    _banner("Test 3 — answer_question (QA without agent)")
    if not index.documents:
        print(f"  {FAIL} — Không có document trong index")
        return False
    title = index.documents[0]["title"]
    question = f"Who authored '{title}'?"
    result = answer_question(question, settings, index)
    ok = (
        bool(result.answer)
        and result.answer != "I don't know from the indexed corpus."
        and len(result.retrieved_doc_ids) >= 1
    )
    print(f"  Question        : {question[:70]!r}")
    print(f"  Answer          : {result.answer[:80]!r}")
    print(f"  Retrieved doc_ids: {result.retrieved_doc_ids[:2]}")
    print(f"  {PASS if ok else FAIL}")
    return ok


def test_agent_tool_call(index: LocalEmbeddingIndex, settings) -> bool:
    """
    Test 4: build_agent chạy được.
    Không invoke LLM (tốn quota) — chỉ kiểm tra agent object có thể khởi tạo.
    Để test thực tế, uncomment phần invoke bên dưới.
    """
    _banner("Test 4 — build_agent (khởi tạo)")
    try:
        from retrieval.agent import build_agent
        agent = build_agent(settings, index)
        ok = agent is not None
        print(f"  Agent object   : {type(agent).__name__}")
        print(f"  {PASS if ok else FAIL} — Agent khởi tạo thành công")

        # --- Uncomment để test thực tế (tốn LLM quota) ---
        # from retrieval.agent import run_agent_question
        # title = index.documents[0]["title"]
        # answer = run_agent_question(agent, f"What are the main topics of '{title}'?")
        # print(f"  Agent answer   : {answer[:120]!r}")
        # ok = bool(answer)
        # -------------------------------------------------
    except Exception as exc:
        print(f"  {FAIL} — {exc}")
        ok = False
    return ok


def main() -> None:
    print("\n" + "=" * 60)
    print("  Role 4 · Smoke Test RAG — CP2 Verification")
    print("=" * 60)

    settings = load_settings()

    # Test 0: manifest phải tồn tại trước
    if not test_manifest_exists(settings):
        print("\n⛔ ABORT — Hãy chạy phase1 (uv run python script/run_phase1.py) trước.")
        sys.exit(1)

    # Load index
    print("\n  Loading index từ manifest…")
    index = LocalEmbeddingIndex.load(settings)
    print(f"  Documents loaded: {len(index.documents)}")
    print(f"  Collection      : {index.collection_name}")

    results = {
        "T1 semantic_search": test_semantic_search(index),
        "T2a lookup_by_id"  : test_exact_lookup_id(index),
        "T2b lookup_by_title": test_exact_lookup_title(index),
        "T3 answer_question" : test_answer_question(index, settings),
        "T4 build_agent"     : test_agent_tool_call(index, settings),
    }

    _banner("Tổng kết")
    passed = sum(results.values())
    total  = len(results)
    for name, ok in results.items():
        print(f"  {PASS if ok else FAIL}  {name}")
    print()
    if passed == total:
        print(f"  🎉 Tất cả {total}/{total} tests PASS — Role 4 CP2 sẵn sàng!")
    else:
        print(f"  ⚠️  {passed}/{total} tests pass — kiểm tra lại clean/index contract.")
    print()


if __name__ == "__main__":
    main()
