"""宿題（実装）: 前後ページを付ける処理のテスト（LLMもAPIキーも使わない）。"""

from app.retrieval import add_neighbor_pages, load_pages

PAGES = load_pages()
BY_ID = {page["page_id"]: page for page in PAGES}


def hit(page_id: str, distance: float = 0.1) -> dict:
    """検索DBが返す1件と同じ形の検索結果を作る。"""
    return {**BY_ID[page_id], "distance": distance}


def ids(results: list[dict]) -> list[str]:
    return [result["page_id"] for result in results]


def test_window_zero_keeps_hits_unchanged():
    results = add_neighbor_pages([hit("lec02-main-p052")], window=0)
    assert ids(results) == ["lec02-main-p052"]


def test_adds_previous_and_next_page_in_page_order():
    results = add_neighbor_pages([hit("lec02-main-p052")], window=1)
    assert ids(results) == ["lec02-main-p051", "lec02-main-p052", "lec02-main-p053"]
    assert [r["role"] for r in results] == ["neighbor", "hit", "neighbor"]
    assert results[0]["neighbor_of"] == "lec02-main-p052"
    assert results[0]["content"]  # 前後ページにも本文と引用情報が付く


def test_does_not_duplicate_pages_and_keeps_hit_role():
    # p.52とp.51がどちらも検索で一致した場合、p.51は1回だけ、検索結果として返す
    results = add_neighbor_pages([hit("lec02-main-p052", 0.1), hit("lec02-main-p051", 0.2)], window=1)
    assert len(ids(results)) == len(set(ids(results)))
    assert ids(results) == ["lec02-main-p051", "lec02-main-p052", "lec02-main-p053", "lec02-main-p050"]
    p051 = results[0]
    assert p051["role"] == "hit" and p051["distance"] == 0.2


def test_does_not_cross_documents():
    # 第2回の1ページ目の前に、第1回の最後のページを付けない
    first = add_neighbor_pages([hit("lec02-main-p001")], window=1)
    assert ids(first) == ["lec02-main-p001", "lec02-main-p002"]
    last_page = max(p["page"] for p in PAGES if p["document_id"] == "lec01-main")
    last = add_neighbor_pages([hit(f"lec01-main-p{last_page:03d}")], window=1)
    assert all(r["document_id"] == "lec01-main" for r in last)
    assert len(last) == 2
