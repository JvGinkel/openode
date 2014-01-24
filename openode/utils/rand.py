# -*- coding: utf-8 -*-


def generate_random_string(length, chars=[[97, 122], [65, 90], [48, 57]], remove_chars=[]):
    #chars napr.: [[97,122],[65,90],[48,57]] - mala pismena + velka pismena + cisla
    #chars napr.: [[97,99],[101],[103,104]] - abc + e + gh
    from random import choice
    ch = ''
    r = ''
    for seq in chars:
        if len(seq) == 1:
            ch += chr(seq[0])
        elif len(seq) == 2:
            for i in range(seq[0], seq[1] + 1):
                if i not in remove_chars:
                    ch += chr(i)
    for i in range(length):
        r += choice(ch)
    return r
