import configparser

from ordhjaelp.platform.linux.install import render_desktop_file


def test_desktop_file_is_valid() -> None:
    content = render_desktop_file("/usr/bin/ordhjaelp")
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    parser.read_string(content)
    entry = parser["Desktop Entry"]
    assert entry["Exec"] == "/usr/bin/ordhjaelp start"
    assert entry["Name"] == "Ordhjælp"
    assert "@" not in content
