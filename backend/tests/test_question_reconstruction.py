from app.knowledge.extractor import reconstruct_question_candidates
from app.knowledge.models import PageExtraction


def test_question_reconstruction_keeps_cross_page_boundary_exact():
    pages = [
        PageExtraction(
            page_number=1,
            text="1. A particle starts moving.\n(A) 10\n(B) 20",
            image_count=0,
            block_count=1,
        ),
        PageExtraction(
            page_number=2,
            text="(C) 30\n(D) 40\n2. A new question starts here.\n(A) 1\n(B) 2",
            image_count=0,
            block_count=1,
        ),
    ]

    questions = reconstruct_question_candidates(pages)

    assert len(questions) == 2
    assert questions[0].number == "1"
    assert questions[0].page_start == 1
    assert questions[0].page_end == 2
    assert "(C) 30" in questions[0].text
    assert questions[1].number == "2"
    assert questions[1].page_start == 2
    assert questions[1].page_end == 2


def test_question_reconstruction_does_not_extend_previous_question_to_next_page():
    pages = [
        PageExtraction(
            page_number=1,
            text="1. Complete question?\n(A) 1\n(B) 2",
            image_count=0,
            block_count=1,
        ),
        PageExtraction(
            page_number=2,
            text="2. Next question?\n(A) 3\n(B) 4",
            image_count=0,
            block_count=1,
        ),
    ]

    questions = reconstruct_question_candidates(pages)

    assert [(q.page_start, q.page_end) for q in questions] == [(1, 1), (2, 2)]
