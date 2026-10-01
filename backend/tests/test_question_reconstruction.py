from app.knowledge.extractor import PageExtraction, reconstruct_question_candidates


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


def test_numbered_options_do_not_start_new_questions():
    pages = [
        PageExtraction(
            page_number=1,
            text="1. Which value is correct?\n1) 4\n2) 5\n3) 6\n4) 7",
            image_count=0,
            block_count=1,
        ),
        PageExtraction(
            page_number=2,
            text="2. Find the integer value of x.\n12",
            image_count=0,
            block_count=1,
        ),
    ]

    questions = reconstruct_question_candidates(pages)

    assert len(questions) == 2
    assert questions[0].number == "1"
    assert "2) 5" in questions[0].text
    assert questions[1].number == "2"


def test_answer_key_extraction_maps_numbered_choices_and_numerical_answers():
    from app.knowledge.service import KnowledgeService

    pages = [
        PageExtraction(
            page_number=9,
            text="ANSWER KEY\n1. B\n2 - 3.14\n3: 7\n4 A",
            image_count=0,
            block_count=1,
        )
    ]

    answers = KnowledgeService._extract_answer_key(pages)

    assert answers["1"] == "B"
    assert answers["2"] == "3.14"
    assert answers["3"] == "7"
    assert answers["4"] == "A"
