from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TopicDefinition:
    code: str
    title: str


@dataclass(frozen=True, slots=True)
class ChapterDefinition:
    term_code: str
    term_title: str
    code: str
    title: str
    pdf_name: str
    topics: tuple[TopicDefinition, ...]


# Only verified numbered headings are enabled. Summary-derived subtopics are
# intentionally absent until separately approved.
CLASS_8_CHAPTERS: tuple[ChapterDefinition, ...] = (
    ChapterDefinition("term_1", "Term 1", "1", "A Square and A Cube", "hegp101.pdf", (
        TopicDefinition("1.1", "Square Numbers"), TopicDefinition("1.2", "Cubic Numbers"),
        TopicDefinition("1.3", "A Pinch of History"),
    )),
    ChapterDefinition("term_1", "Term 1", "2", "Power Play", "hegp102.pdf", (
        TopicDefinition("2.1", "Experiencing the Power Play"), TopicDefinition("2.2", "Exponential Notation and Operations"),
        TopicDefinition("2.3", "The Other Side of Powers"), TopicDefinition("2.4", "Powers of 10"),
        TopicDefinition("2.5", "Did You Ever Wonder?"),
    )),
    ChapterDefinition("term_1", "Term 1", "3", "A Story of Numbers", "hegp103.pdf", (
        TopicDefinition("3.1", "Reema's Curiosity"), TopicDefinition("3.2", "Some Early Number Systems"),
        TopicDefinition("3.3", "The Idea of a Base"),
    )),
    ChapterDefinition("term_1", "Term 1", "4", "Quadrilaterals", "hegp104.pdf", (
        TopicDefinition("4.1", "Rectangles and Squares"), TopicDefinition("4.2", "Angles in a Quadrilateral"),
        TopicDefinition("4.3", "More Quadrilaterals with Parallel Opposite Sides"), TopicDefinition("4.4", "Quadrilaterals with Equal Sidelengths"),
        TopicDefinition("4.5", "Playing with Quadrilaterals"), TopicDefinition("4.6", "Kite and Trapezium"),
    )),
    ChapterDefinition("term_1", "Term 1", "5", "Number Play", "hegp105.pdf", (
        TopicDefinition("5.1", "Is This a Multiple Of?"), TopicDefinition("5.2", "Checking Divisibility Quickly"),
        TopicDefinition("5.3", "Digits in Disguise"),
    )),
    ChapterDefinition("term_1", "Term 1", "6", "We Distribute, Yet Things Multiply", "hegp106.pdf", (
        TopicDefinition("6.1", "Some Properties of Multiplication"), TopicDefinition("6.2", "Special Cases of the Distributive Property"),
        TopicDefinition("6.3", "Mind the Mistake, Mend the Mistake"), TopicDefinition("6.4", "This Way or That Way, All Ways Lead to the Bay"),
    )),
    ChapterDefinition("term_1", "Term 1", "7", "Proportional Reasoning-1", "hegp107.pdf", (
        TopicDefinition("7.1", "Observing Similarity in Change"), TopicDefinition("7.2", "Ratios"),
        TopicDefinition("7.3", "Ratios in their Simplest Form"), TopicDefinition("7.4", "Problem Solving with Proportional Reasoning"),
        TopicDefinition("7.5", "Sharing, but Not Equally!"), TopicDefinition("7.6", "Unit Conversions"),
    )),
    ChapterDefinition("term_2", "Term 2", "1", "Fractions in Disguise", "hegp201.pdf", (
        TopicDefinition("1.1", "Fractions as Percentages"), TopicDefinition("1.2", "Percentage of Some Quantity"),
        TopicDefinition("1.3", "Using Percentages"),
    )),
    ChapterDefinition("term_2", "Term 2", "2", "The Baudhāyana-Pythagoras Theorem", "hegp202.pdf", (
        TopicDefinition("2.1", "Doubling a Square"), TopicDefinition("2.2", "Halving a Square"),
        TopicDefinition("2.3", "Hypotenuse of an Isosceles Right Triangle"), TopicDefinition("2.4", "Combining Two Different Squares"),
        TopicDefinition("2.5", "Right-Triangles Having Integer Sidelengths"), TopicDefinition("2.6", "A Long-Standing Open Problem"),
        TopicDefinition("2.7", "Further Applications of the Baudhāyana-Pythagoras Theorem"),
    )),
    ChapterDefinition("term_2", "Term 2", "3", "Proportional Reasoning-2", "hegp203.pdf", (
        TopicDefinition("3.1", "Proportionality - A Quick Recap"), TopicDefinition("3.2", "Ratios in Maps"),
        TopicDefinition("3.3", "Ratios with More than 2 Terms"), TopicDefinition("3.4", "Dividing a Whole in a Given Ratio"),
        TopicDefinition("3.5", "A Slice of the Pie"), TopicDefinition("3.6", "Inverse Proportions"),
    )),
    ChapterDefinition("term_2", "Term 2", "4", "Exploring Some Geometric Themes", "hegp204.pdf", (
        TopicDefinition("4.1", "Fractals"), TopicDefinition("4.2", "Visualising Solids"),
    )),
    ChapterDefinition("term_2", "Term 2", "5", "Tales by Dots and Lines", "hegp205.pdf", (
        TopicDefinition("5.1", "The Balancing Act"), TopicDefinition("5.2", "Visualising and Interpreting Data"),
    )),
    ChapterDefinition("term_2", "Term 2", "6", "Algebra Play", "hegp206.pdf", (
        TopicDefinition("6.1", "Algebra Play"), TopicDefinition("6.2", "Thinking about 'Think of a Number' Tricks"),
        TopicDefinition("6.3", "Number Pyramids"), TopicDefinition("6.4", "Fun with Grids"),
        TopicDefinition("6.5", "The Largest Product"), TopicDefinition("6.6", "Decoding Divisibility Tricks"),
    )),
    ChapterDefinition("term_2", "Term 2", "7", "Area", "hegp207.pdf", (
        TopicDefinition("7.1", "Rectangles and Squares"),
    )),
)


def chapter_by_pdf(pdf_name: str) -> ChapterDefinition:
    for chapter in CLASS_8_CHAPTERS:
        if chapter.pdf_name.casefold() == pdf_name.casefold():
            return chapter
    raise KeyError(f"Unapproved textbook PDF: {pdf_name}")
