from html.parser import HTMLParser
import time
import urllib.request


class FeedParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_feed = False
        self.in_item = False
        self.finished = False
        self.capture = None
        self.fields = {'text': [], 'kind': [], 'time': []}
        self.url = ''

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get('id') == 'feed-list':
            self.in_feed = True
        if self.in_feed and not self.finished and tag == 'li' and not self.in_item:
            self.in_item = True
        if not self.in_item:
            return
        classes = attrs.get('class', '').split()
        if tag == 'p' and 'feed-text' in classes:
            self.capture = ('text', 'p')
        elif tag == 'span' and 'chip' in classes and not self.capture:
            self.capture = ('kind', 'span')
        elif tag == 'a' and 'feed-time' in classes:
            self.capture = ('time', 'a')
            self.url = attrs.get('href', '')

    def handle_data(self, data):
        if self.in_item and self.capture:
            self.fields[self.capture[0]].append(data)

    def handle_endtag(self, tag):
        if self.capture and self.capture[1] == tag:
            self.capture = None
        if tag == 'li' and self.in_item:
            self.in_item = False
            self.finished = True
        if tag == 'ul':
            self.in_feed = False


def parse_feed(html):
    parser = FeedParser()
    parser.feed(html)
    fields = {key: ' '.join(''.join(value).split()) for key, value in parser.fields.items()}
    if not fields['text'] or not parser.url.startswith('https://x.com/thsottiaux/status/'):
        raise ValueError('最新帖子结构已变化')
    return dict(fields, url=parser.url, at=time.time(), source='https://codex-reset.com/')


def fetch_feed():
    request = urllib.request.Request('https://codex-reset.com/', headers={'User-Agent': 'TokenView/0.1 (+local personal quota viewer)'})
    with urllib.request.urlopen(request, timeout=20) as response:
        page = response.read(2 * 1024 * 1024 + 1)
    if len(page) > 2 * 1024 * 1024:
        raise ValueError('帖子页面过大')
    return parse_feed(page.decode('utf-8'))
