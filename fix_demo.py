
import re

with open('web.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("from core.models import Position", "from core.state import OptionPosition")
content = content.replace("fake_pos = Position(", "fake_pos = OptionPosition(")

with open('web.py', 'w', encoding='utf-8') as f:
    f.write(content)
