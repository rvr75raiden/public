#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Markdown to Pixiv / Hameln Novel Formatter
Markdown形式の小説原稿をPixiv小説記法およびハーメルン装飾タグに変換するスクリプト
"""

import os
import re
import sys
import argparse
from typing import Dict, Tuple, List, Optional


class NovelConverter:
    """Markdown小説をPixivおよびハーメルン向けに変換するクラス"""

    RUBY_REGEX = re.compile(
        r'<ruby>(?:<rb>)?([\s\S]+?)(?:</rb>)?(?:<rp>[\s\S]*?</rp>)?<rt>([\s\S]+?)</rt>(?:<rp>[\s\S]*?</rp>)?</ruby>'
    )
    TITLE_REGEX = re.compile(r'^#\s+(.+)$', re.MULTILINE)
    CODE_FENCE_REGEX = re.compile(r'```(?:[a-zA-Z0-9_-]*\r?\n)?([\s\S]*?)```')
    CHAPTER_REGEX = re.compile(r'^##\s+(.+)$', re.MULTILINE)
    HR_REGEX = re.compile(r'^(?:[-*_]\s*){3,}$', re.MULTILINE)
    BOLD_REGEX = re.compile(r'\*\*(.+?)\*\*')
    ITALIC_REGEX = re.compile(r'(?<!\*)\*([^*]+?)\*(?!\*)')
    STRIKE_REGEX = re.compile(r'~~(.+?)~~')

    def __init__(self, options: Optional[Dict] = None):
        self.options = {
            'pixiv_first_newpage': False,  # 1章目（先頭）に [newpage] を付与するか（Pixivで先頭が空ページになるのを防ぐためデフォルトFalse）
            'pixiv_remove_bold': False,    # Pixivでは太字記法がないため ** を除去するか
            'hameln_convert_bold': True,   # **太字** を 《b》太字《/b》 に変換
            'hameln_convert_italic': True, # *斜体* を 《i》斜体《/i》 に変換
            'hameln_convert_strike': True, # ~~取消~~ を 《s》取消《/s》 に変換
            'hameln_convert_hr': True,     # 水平線を 《hr》 に変換
            'trim_trailing_spaces': True,  # 各行末の空白を除去
            'compress_blank_lines': True,  # 3行以上の連続空行を2行に圧縮
            'include_title_in_body': False, # 本文先頭にタイトルを含めるか（投稿フォームのタイトル欄と重複させないためデフォルトFalse）
            'include_caption_in_body': False, # 本文先頭にキャプションを含めるか
        }
        if options:
            self.options.update(options)

    def parse_markdown(self, md_text: str) -> Tuple[str, str, str]:
        """
        Markdownテキストからタイトル、キャプション、本文を抽出・分離する。
        戻り値: (title, caption_text, clean_body)
        """
        # 1. タイトル抽出 (# タイトル)
        title = ""
        title_match = self.TITLE_REGEX.search(md_text)
        if title_match:
            title = title_match.group(1).strip()
            # 本文からタイトル行を除去
            body = self.TITLE_REGEX.sub('', md_text, count=1)
        else:
            body = md_text

        # 2. キャプション抽出 (``` で囲まれたコードブロック)
        captions: List[str] = []
        for match in self.CODE_FENCE_REGEX.finditer(body):
            content = match.group(1).strip()
            if content:
                captions.append(content)
        caption_text = "\n\n".join(captions)
        # 本文からコードブロックを除去
        body = self.CODE_FENCE_REGEX.sub('', body)

        # 先頭の不要な改行をトリム
        body = body.lstrip('\r\n')

        return title, caption_text, body

    def convert_to_pixiv(self, md_text: str) -> Dict[str, str]:
        """
        Pixivフォーマットに変換する。
        """
        title, caption, body = self.parse_markdown(md_text)

        # 1. ルビ変換: <ruby><rb>親文字</rb><rt>ルビ</rt></ruby> -> [[rb:親文字 > ルビ]]
        body = self.RUBY_REGEX.sub(r'[[rb:\1 > \2]]', body)

        # 2. 章タイトル変換: ## 章名 -> [newpage]\n[chapter:章名]
        chapter_idx = [0]
        # 本文の先頭に文字があるかどうか（1章目の前に文章があるか）
        first_chapter_match = self.CHAPTER_REGEX.search(body)
        has_text_before_first_chapter = False
        if first_chapter_match:
            prefix = body[:first_chapter_match.start()].strip()
            has_text_before_first_chapter = len(prefix) > 0

        def replace_pixiv_chapter(match):
            chapter_idx[0] += 1
            ch_name = match.group(1).strip()
            # 1章目で、かつ1章目より前に本文がなく、pixiv_first_newpageがFalseの場合は改ページ不要
            if chapter_idx[0] == 1 and not has_text_before_first_chapter and not self.options['pixiv_first_newpage']:
                return f"[chapter:{ch_name}]"
            return f"[newpage]\n[chapter:{ch_name}]"

        body = self.CHAPTER_REGEX.sub(replace_pixiv_chapter, body)

        # 3. 太字の処理（オプション）
        if self.options['pixiv_remove_bold']:
            body = self.BOLD_REGEX.sub(r'\1', body)

        # 4. 空行・スペース整形
        body = self._clean_text(body)

        # 本文先頭への組み込み（オプション）
        final_body_parts = []
        if self.options['include_title_in_body'] and title:
            final_body_parts.append(title)
        if self.options['include_caption_in_body'] and caption:
            final_body_parts.append(caption)
        final_body_parts.append(body)
        final_body = "\n\n".join([p for p in final_body_parts if p]).strip()

        # 全部つなげたテキスト
        all_parts = []
        if title:
            all_parts.append(f"【タイトル】\n{title}")
        if caption:
            all_parts.append(f"【キャプション】\n{caption}")
        all_parts.append(f"【本文】\n{final_body}")
        full_text = "\n\n" + ("=" * 40) + "\n\n".join(all_parts)

        return {
            'target': 'pixiv',
            'title': title,
            'caption': caption,
            'body': final_body,
            'full_text': "\n\n".join(all_parts),
        }

    def convert_to_hameln(self, md_text: str) -> Dict[str, str]:
        """
        ハーメルンフォーマットに変換する。
        """
        title, caption, body = self.parse_markdown(md_text)

        # 1. ルビ変換: <ruby><rb>親文字</rb><rt>ルビ</rt></ruby> -> |親文字《ルビ》
        body = self.RUBY_REGEX.sub(r'|\1《\2》', body)

        # 2. 章タイトル変換: ## 章名 -> 《big》《b》■章名《/b》《/big》《hr》
        def replace_hameln_chapter(match):
            ch_name = match.group(1).strip()
            return f"《big》《b》■{ch_name}《/b》《/big》《hr》"

        body = self.CHAPTER_REGEX.sub(replace_hameln_chapter, body)

        # 3. Markdown記法の変換
        if self.options['hameln_convert_bold']:
            body = self.BOLD_REGEX.sub(r'《b》\1《/b》', body)
        if self.options['hameln_convert_italic']:
            body = self.ITALIC_REGEX.sub(r'《i》\1《/i》', body)
        if self.options['hameln_convert_strike']:
            body = self.STRIKE_REGEX.sub(r'《s》\1《/s》', body)
        if self.options['hameln_convert_hr']:
            body = self.HR_REGEX.sub('《hr》', body)

        # 4. 空行・スペース整形
        body = self._clean_text(body)

        # 本文先頭への組み込み（オプション）
        final_body_parts = []
        if self.options['include_title_in_body'] and title:
            final_body_parts.append(f"《big》《b》{title}《/b》《/big》《hr》")
        if self.options['include_caption_in_body'] and caption:
            final_body_parts.append(f"《b》【あらすじ】《/b》\n{caption}\n《hr》")
        final_body_parts.append(body)
        final_body = "\n\n".join([p for p in final_body_parts if p]).strip()

        # 全部つなげたテキスト
        all_parts = []
        if title:
            all_parts.append(f"【タイトル】\n{title}")
        if caption:
            all_parts.append(f"【あらすじ / 前書き】\n{caption}")
        all_parts.append(f"【本文】\n{final_body}")

        return {
            'target': 'hameln',
            'title': title,
            'caption': caption,
            'body': final_body,
            'full_text': "\n\n".join(all_parts),
        }

    def _clean_text(self, text: str) -> str:
        """余分なスペースや空行を整理する"""
        lines = text.splitlines()
        if self.options['trim_trailing_spaces']:
            lines = [line.rstrip() for line in lines]

        cleaned = "\n".join(lines)
        if self.options['compress_blank_lines']:
            cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)

        return cleaned.strip()


def main():
    parser = argparse.ArgumentParser(description="Markdown 小説 -> Pixiv / ハーメルン 変換ツール")
    parser.add_argument("input_file", nargs="?", help="変換するMarkdownファイルパス")
    parser.add_argument("-t", "--target", choices=["all", "pixiv", "hameln"], default="all", help="変換先フォーマット (default: all)")
    parser.add_argument("-o", "--output-dir", help="出力先ディレクトリ (省略時は入力ファイルと同じ場所)")
    parser.add_argument("--first-newpage", action="store_true", help="Pixiv: 最初の章にも [newpage] を付与する")
    parser.add_argument("--include-title", action="store_true", help="本文の先頭にタイトルを含める")
    parser.add_argument("--include-caption", action="store_true", help="本文の先頭にキャプションを含める")

    args = parser.parse_args()

    if not args.input_file:
        print("使用法: python novel_converter.py <入力Markdownファイル> [オプション]")
        print("例: python novel_converter.py 36_聖都の夜に魔剣は吠える_07.md")
        sys.exit(0)

    if not os.path.exists(args.input_file):
        print(f"エラー: ファイル '{args.input_file}' が見つかりません。", file=sys.stderr)
        sys.exit(1)

    with open(args.input_file, "r", encoding="utf-8") as f:
        md_text = f.read()

    options = {
        'pixiv_first_newpage': args.first_newpage,
        'include_title_in_body': args.include_title,
        'include_caption_in_body': args.include_caption,
    }
    converter = NovelConverter(options)

    base_name = os.path.splitext(os.path.basename(args.input_file))[0]
    out_dir = args.output_dir if args.output_dir else os.path.dirname(os.path.abspath(args.input_file))
    os.makedirs(out_dir, exist_ok=True)

    targets = ["pixiv", "hameln"] if args.target == "all" else [args.target]

    for t in targets:
        if t == "pixiv":
            res = converter.convert_to_pixiv(md_text)
            out_path = os.path.join(out_dir, f"{base_name}_pixiv.txt")
        else:
            res = converter.convert_to_hameln(md_text)
            out_path = os.path.join(out_dir, f"{base_name}_hameln.txt")

        # 本文ファイルを保存
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(res['body'])

        print(f"\n==========================================")
        print(f"【{t.upper()} 変換完了】: {out_path}")
        print(f"==========================================")
        print(f"■ タイトル: {res['title']}")
        if res['caption']:
            print(f"■ キャプション/あらすじ: {res['caption'][:50]}..." if len(res['caption']) > 50 else f"■ キャプション/あらすじ: {res['caption']}")
        print(f"■ 本文字数: {len(res['body'])} 文字")
        print(f"------------------------------------------")
        print("冒頭 300 文字プレビュー:")
        print(res['body'][:300])
        print("...")


if __name__ == "__main__":
    main()
