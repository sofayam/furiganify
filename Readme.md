 have a japanese epub and i want to add the little hiragana pronunciation hints to it


Thought for 5s
Thought for 5s
Yes, that's doable. The hints are called furigana, and in an EPUB they're done with <ruby> tags:

html
<ruby>漢字<rt>かんじ</rt></ruby>
The process is to unzip the EPUB, run through each chapter's XHTML file, find the kanji in the text (leaving existing tags, images, and any ruby that's already there alone), look up each word's reading with a Japanese morphological analyzer (e.g. fugashi with UniDic), wrap the kanji in ruby tags, and re-zip it. The tricky part is words with okurigana, like 食べる, where only the 食 should get the reading, and the analyzer has to pick the right reading from context (e.g. 生 and 日本 have several).

Most e-readers display this properly, including Apple Books, Kobo, and Kindle (if you convert afterwards), though some reader apps need ruby support turned on.

I can do this for you if you upload the EPUB here. It needs to be DRM-free, since I can't process protected files. One question first: do you want furigana on every kanji, or only on the less common ones, so it doesn't clutter easy words? If you're not sure, I'll default to everything beyond the basic school-level kanji (roughly JLPT N5-N4), which is a common choice for learners.

------

furigana on every single one please


Ran 4 commands, read a file
Ran 4 commands, read a file
The EPUB is DRM-free and already has furigana on some of the harder kanji. I'm writing a script that keeps those and adds readings to every other kanji.


Ran a command
Ran a command
The alignment works. Two readings come out wrong: 日本 as にっぽん (I'll override it to にほん) and one 行った as おこなった. I'll apply the override and run the whole book.


Ran 2 commands, shared files · 1 note
Ran 2 commands, shared files · 1 note
Your EPUB now has furigana on every kanji in the body text. I haven't opened it in a reader, but the archive checks out and no bare kanji are left. You can download it as kinonoLu_II_furigana.epub.

Existing furigana: The book already had readings on the harder kanji, about 4,000 of them, and I left those exactly as they were. The new readings, around 11,500, fill in everything else.
Okurigana: Readings sit only over the kanji, so 食べる becomes 食 with た over it and べる left plain.
Accuracy: The readings come from a Japanese morphological analyzer, which gets most words right from context but not all. I fixed 日本 to にほん, but expect occasional wrong readings, such as 行った read as おこなった instead of いった, and some unusual names or stylised words.
Old spellings: The original furigana uses full-size kana where modern spelling has small ones (e.g. ちや, しよく). I left those alone, so they won't match the new readings.
Not changed: Titles in the table of contents and metadata don't have furigana.
If your reader doesn't show the readings, check for a ruby or furigana setting. If you spot readings that look wrong, tell me which ones and I can correct them across the whole book.

----

i want to do this offline. can you give me the program you made?


Created a file, ran a command, shared files · 1 note
Created a file, ran a command, shared files · 1 note
Here's the program: epub_furigana.py. I ran it on your EPUB just now and the output was valid, with no bare kanji left. It's a single self-contained script.

Setup (once, needs internet only for this step):

pip install lxml fugashi unidic-lite
Usage:

python epub_furigana.py book.epub
python epub_furigana.py book.epub book_with_furigana.epub
If you leave out the second filename, it writes book_furigana.epub next to the original.

Existing furigana: Any ruby already in the book is left alone, and everything else gets a reading.
Other files: It converts every XHTML file in the book, including the table-of-contents page (nav.xhtml), which my earlier run skipped. It copies images, CSS and metadata through unchanged. That's why the ruby count is slightly higher than in the file I gave you before.
Fixing readings: At the top of the script is a READING_OVERRIDES dictionary, currently just "日本": "にほん". Add entries like "行": "い" there for words the analyzer gets wrong. The override applies to the whole token, so it's best for words that are wrong everywhere. It won't fix a word that is right in some places and wrong in others, like 行った.
Larger dictionary: unidic-lite is the small dictionary. If you want somewhat better accuracy, you can install the full unidic package (pip install unidic && python -m unidic download, about 1 GB). The script uses whichever dictionary fugashi finds, with no code changes.
It only works on DRM-free EPUBs, and it needs Python 3.8 or newer.

---

could you give me a switch to just do the difficult ones?


Ran 5 commands
Ran 5 commands
The --skip modes all work: the ruby count drops from 15,605 with every kanji to 8,532 at n4 and 3,537 at n2. I'm now checking a sample paragraph at n4 to confirm the right kanji are skipped.


Ran a command, shared files
Ran a command, shared files
I've added a --skip switch to epub_furigana.py, which leaves out furigana on kanji you probably already know. I tested every mode on your EPUB and the output files were valid.

python epub_furigana.py book.epub                  # every kanji (default, same as before)
python epub_furigana.py book.epub --skip n4        # skip JLPT N5 + N4 kanji
python epub_furigana.py book.epub out.epub --skip g3   # skip school grades 1-3
python epub_furigana.py book.epub --skip n4 --known-kanji 鬼魔   # plus your own extras
Levels: n5, n4, n3 and n2 skip every kanji up to that JLPT level. g1 to g6 skip up to that Japanese school grade. --known-kanji adds your own extras. I built the kanji lists from a community dataset and embedded them in the script, so it still runs fully offline. Kanji that aren't on any list always get furigana.

Whole words: A kanji word is annotated if any kanji in it is above your level. At n4, 学校 stays plain, but a word like 学園 is annotated as a whole. This keeps compound readings intact.

How much it changes: On your book, the ruby count goes from 15,605 with every kanji to 8,532 at n4 and 3,537 at n2. In a sample paragraph at n4, common kanji like 道, 走 and 雨 were left plain, while 沼 and 縫 got readings. 進 also got one, since it's N3.

Existing furigana in the book is never removed, so --skip only affects the readings the script adds. The original furigana still sits on some easy kanji too.


