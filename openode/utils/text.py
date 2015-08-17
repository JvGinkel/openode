# -*- coding: utf-8 -*-
"""
    If will some problem with regular exp., you can try this link
    http://stackoverflow.com/questions/827557/how-do-you-validate-a-url-with-a-regular-expression-in-python
    for complete url parsing.
"""
import re

url_reg = r'(https?://[-A-Za-z0-9+&@#/%?=~_()|!:,.;]*[-A-Za-z0-9+&@#/%=~_|])'
get_urllist_from_text = lambda text: re.findall(url_reg, text)


def extract_numbers(str):
    return [
        int(_id) for _id in
        re.findall(r"\d+", str)
    ]
