import pytest

from woob.tools.misc import clean_text


@pytest.mark.parametrize(
    "src,output",
    (
        ("hello  world", "hello world"),
        ("\thello \n world  ", "hello world"),
        ("je suis tomb\u0065\u0301\n", "je suis tomb\u00e9"),
        ("je suis tomb\u00e9\u00e9\n", "je suis tomb\u00e9\u00e9"),
    ),
)
def test_clean_text(src, output):
    """Test basic cases for :py:func:`woob.tools.misc.clean_text`."""
    assert clean_text(src) == output


@pytest.mark.parametrize("src,output", (("hello \n world \r\nwow!!   ", "hello\nworld\nwow!!"),))
def test_clean_text_keep_newlines(src, output):
    """Test clean text while keeping newlines."""
    assert clean_text(src, remove_newlines=False) == output


@pytest.mark.parametrize(
    "src,output",
    (
        ("je suis tomb\u0065\u0301\n", "je suis tombe"),
        ("je suis tomb\u00e9", "je suis tombe"),
    ),
)
def test_clean_text_transliterate(src, output):
    """Test clean text without transliteration."""
    assert clean_text(src, transliterate=True) == output
