import json
import os
import re
import threading
import time
import urllib.parse
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

import wx
import xmltodict
from markdownify import markdownify as md
from pathvalidate import sanitize_filename

p_server = re.compile(r'(imglf\d?)', re.I)

p_img = re.compile(r'<img src="([^"]+?)"([^>]*)>', re.I)

p_ext_img = re.compile(r'<img src="([^"]+?)"[^>]*>', re.I)

gh_prefix = 'raw.githubusercontent.com'

# LOFTER-墨问非名-2019.03.29.xml
p_lofter = re.compile(r'^LOFTER-(.*)-(\d{4}\.\d{2}\.\d{2})')

header = '''<?xml version="1.0" encoding="UTF-8" ?>
<!-- This is a WordPress eXtended RSS file generated by WordPress as an export of your site. -->
<!-- It contains information about your site's posts, pages, comments, categories, and other content. -->
<!-- You may use this file to transfer that content from one site to another. -->
<!-- This file is not intended to serve as a complete backup of your site. -->

<!-- To import this information into a WordPress site follow these steps: -->
<!-- 1. Log in to that site as an administrator. -->
<!-- 2. Go to Tools: Import in the WordPress admin panel. -->
<!-- 3. Install the "WordPress" importer from the list. -->
<!-- 4. Activate & Run Importer. -->
<!-- 5. Upload this file using the form provided on that page. -->
<!-- 6. You will first be asked to map the authors in this export file to users -->
<!--    on the site. For each author, you may choose to map to an -->
<!--    existing user on the site or to create a new user. -->
<!-- 7. WordPress will then import each of the posts, pages, comments, categories, etc. -->
<!--    contained in this file into your site. -->

<!-- generator="WordPress.com" created="2019-06-08 20:37"-->
<rss version="2.0"
	xmlns:excerpt="http://wordpress.org/export/1.2/excerpt/"
	xmlns:content="http://purl.org/rss/1.0/modules/content/"
	xmlns:wfw="http://wellformedweb.org/CommentAPI/"
	xmlns:dc="http://purl.org/dc/elements/1.1/"
	xmlns:wp="http://wordpress.org/export/1.2/"
>
'''

channel_header = '''<channel>
<title>lolirabbit</title>
<link>https://lolirabbit.wordpress.com</link>
<description></description>
<pubDate>Sat, 08 Jun 2019 20:37:37 +0000</pubDate>
<language></language>
<wp:wxr_version>1.2</wp:wxr_version>
<wp:base_site_url>http://wordpress.com/</wp:base_site_url>
<wp:base_blog_url>https://lolirabbit.wordpress.com</wp:base_blog_url>
<wp:author>
<wp:author_id>82339102</wp:author_id>
<wp:author_login>
<![CDATA[anywaywillgo]]>
</wp:author_login>
<wp:author_email>
<![CDATA[anywaywillgo@gmail.com]]>
</wp:author_email>
<wp:author_display_name>
<![CDATA[anywaywillgo]]>
</wp:author_display_name>
<wp:author_first_name>
<![CDATA[]]>
</wp:author_first_name>
<wp:author_last_name>
<![CDATA[]]>
</wp:author_last_name>
</wp:author>
<generator>http://wordpress.com/</generator>
<image>
    <url>http://s0.wp.com/i/buttonw-com.png</url>
    <title>lolirabbit</title>
    <link>https://lolirabbit.wordpress.com</link>
</image>
'''

footer = '''</channel>
</rss>'''

sample_item_a = '''
<wp:comment_status>open</wp:comment_status>
<wp:ping_status>open</wp:ping_status>'''

sample_item_b = '''
<wp:status>publish</wp:status>
<wp:post_parent>0</wp:post_parent>
<wp:menu_order>0</wp:menu_order>
<wp:post_type>post</wp:post_type>
<wp:post_password></wp:post_password>
<wp:is_sticky>0</wp:is_sticky>
'''

sample_item_footer = '''
<wp:postmeta>
    <wp:meta_key>timeline_notification</wp:meta_key>
    <wp:meta_value><![CDATA[1560026174]]></wp:meta_value>
</wp:postmeta>
<wp:postmeta>
    <wp:meta_key>_rest_api_published</wp:meta_key>
    <wp:meta_value><![CDATA[1]]></wp:meta_value>
</wp:postmeta>
<wp:postmeta>
    <wp:meta_key>_rest_api_client_id</wp:meta_key>
    <wp:meta_value><![CDATA[-1]]></wp:meta_value>
</wp:postmeta>
<wp:postmeta>
    <wp:meta_key>_publicize_job_id</wp:meta_key>
    <wp:meta_value><![CDATA[31631303363]]></wp:meta_value>
</wp:postmeta>
</item>
'''
wordpress_prefix = 'https://samplewordpressblog.wordpress.com/'


def get_di_files_w_suffix(rootdir, suffixes):
    file_paths = []
    files = os.listdir(rootdir)
    if isinstance(suffixes, str):
        suffixes = (suffixes,)
    for file in files:
        file_path = Path(rootdir) / file
        if file_path.suffix.lower() in suffixes and file_path.is_file():
            file_paths.append(file_path)
    file_paths.sort()
    return file_paths


def get_di_xml(rootdir):
    suffixes = ".xml"
    return get_di_files_w_suffix(rootdir, suffixes)


# ================创建目录================
def make_dir(file_path):
    if not os.path.exists(file_path):
        try:
            os.mkdir(file_path)
        except:
            pass


# ================运行时间计时================
def run_time(start_time):
    '''
    :param start_time:
    :return: 运行时间
    '''
    run_time = time.time() - start_time
    if run_time < 60:  # 两位小数的秒
        show_run_time = '{:.2f}秒'.format(run_time)
    elif run_time < 3600:  # 分秒取整
        show_run_time = '{:.0f}分{:.0f}秒'.format(run_time // 60, run_time % 60)
    else:  # 时分秒取整
        show_run_time = '{:.0f}时{:.0f}分{:.0f}秒'.format(run_time // 3600, run_time % 3600 // 60, run_time % 60)
    return show_run_time


def list2str(some_list):
    some_string = ''
    if isinstance(some_list, list):
        some_string = "[" + ", ".join(some_list) + "]"
    elif isinstance(some_list, str):
        some_string = some_list
    return some_string


def format_hugo_title(title):
    if "'" in title or "#" in title or "@" in title or "[" in title or "]" in title or "+" in title or "!" in title or ":" in title or title.isdigit():  # or "：" in title or "（" in title or "）" in title
        title_info = '"' + title + '"'
    else:
        title_info = title
    return title_info


def safe(title):
    safe_title = title.replace(':', '：')
    safe_title = safe_title.replace('!', '！')
    safe_title = safe_title.replace("'", "-")
    # safe_title = title.replace("'", "’")
    safe_title = safe_title.replace('/', '／')
    safe_title = safe_title.replace('\\', '＼')
    safe_title = sanitize_filename(safe_title)
    return safe_title


# ================写入文件================
def write_text(file_path, text):
    f = open(file_path, mode='w', encoding="utf-8")
    try:
        f.write(text)
    finally:
        f.close()


def deduce_list(input_list):
    output_list = list(OrderedDict.fromkeys(input_list))
    return output_list


def int2time(timestamp, formatter='%Y-%m-%d %H:%M:%S'):
    timestamp = int(timestamp)
    timestamp = timestamp / 1000
    time_str = datetime.utcfromtimestamp(timestamp).strftime(formatter)

    return time_str


def get_head_matter(export_type, title, publishTime, modifyTime, author, categories, tags, permalink, description=''):
    # ================构造头部================
    content = '---'
    title_info = format_hugo_title(title)

    permalink_lower = permalink.lower()
    slug = '"' + permalink_lower + '"'

    if export_type == 'Hugo':
        publishTime = publishTime.replace(' ', 'T') + '+08:00'
        modifyTime = modifyTime.replace(' ', 'T') + '+08:00'

    content += '\ntitle: ' + title_info
    content += '\ndate: ' + publishTime
    content += '\ntags: ' + list2str(tags)

    if export_type == 'Hexo':
        content += '\ncategories: ' + list2str(categories)
        content += '\nupdated: ' + modifyTime
        content += '\npermalink: ' + permalink
        content += '\nauthor: "' + author + '"'
        content += '\ndescription: "' + description + '"'

    elif export_type == 'Hugo':
        content += '\ncategories: ' + list2str(categories)
        content += '\nlastmod: ' + modifyTime
        content += '\nslug: ' + permalink
        content += '\nauthor: "' + author + '"'
        content += '\ndescription: "' + description + '"'

    elif export_type == 'Jekyll':
        content += '\ncategories: ' + list2str(categories)

    elif export_type == 'Gridea':
        content += '\npublished: true'
        content += '\nhideInList: false'
        content += '\nfeature: '

    content += '\n---'
    return content


def get_comments(post, id2name_dict):
    md_comment_section = ''
    html_comment_section = ''

    commentList = post['commentList']
    comments = commentList['comment']
    if not isinstance(comments, list):
        comments = [comments]
    if comments:
        comments.reverse()

        md_comment_section += '\n\n<!-- more -->\n\n---\n'
        html_comment_section += '\n\n<p><!--more--></p>\n\n<hr />\n'

        for j in range(len(comments)):
            comment = comments[j]
            publisherUserId = comment['publisherUserId']
            publisherNick = comment['publisherNick']
            publisherContent = comment['content']
            commentPublishTime = comment['publishTime']
            commentPublishTime = int2time(commentPublishTime)
            replyToUserId = comment['replyToUserId']
            # decodedpublisherUserId = base64.b64decode(publisherUserId)  # 然而还是乱码……
            # decodedreplyToUserId = base64.b64decode(replyToUserId)  # 然而还是乱码……
            # publisherContentMD = html2text.html2text(publisherContent).strip('\r\n\t ')
            # publisherContentMD = md(publisherContent).strip('\r\n\t ')
            # publisherContentText = html.unescape(publisherContent)

            replyToStr = ''
            if replyToUserId in id2name_dict:
                Nicks = id2name_dict[replyToUserId]
                Nicks_only = [x[0] for x in Nicks]
                Nicks_only = deduce_list(Nicks_only)
                if len(Nicks_only) >= 2:
                    # print(Nicks)
                    pass
                Nicks.sort(key=lambda x: x[-1])
                Nick = Nicks[-1][0]
                replyToStr = ' 回复【' + md(Nick) + '】'

            md_line = '\n`' + commentPublishTime + '` 【' + md(publisherNick) + '】' + replyToStr + ' ' + md(
                publisherContent) + '\n'
            html_line = '\n<p><code>' + commentPublishTime + '</code> 【' + publisherNick + '】' + replyToStr + ' ' + publisherContent + '</p>\n'

            md_comment_section += md_line
            html_comment_section += html_line
    return md_comment_section, html_comment_section


def get_id2name_dict(doc):
    id2name_dict = {}
    posts = doc['lofterBlogExport']['PostItem']

    if not isinstance(posts, list):
        posts = [posts]

    posts.reverse()
    for i in range(len(posts)):
        post = posts[i]
        if 'commentList' in post:
            commentList = post['commentList']
            comments = commentList['comment']
            if not isinstance(comments, list):
                comments = [comments]
            for j in range(len(comments)):
                comment = comments[j]
                publisherUserId = comment['publisherUserId']
                publisherNick = comment['publisherNick']
                commentPublishTime = comment['publishTime']
                commentPublishTime = int2time(commentPublishTime)
                if publisherUserId not in id2name_dict:
                    id2name_dict[publisherUserId] = []
                tup = (publisherNick, commentPublishTime)
                id2name_dict[publisherUserId].append(tup)
    return id2name_dict


def get_item_str(i, title, publishTime, modifyTime, author, categories, tags, permalink, html_content):
    item_str = '<item>'
    link = wordpress_prefix + permalink
    pubDate = ''
    description = ''
    excerpt = ''
    post_id = 2 * i + 1
    post_date = publishTime
    post_date_gmt = publishTime
    item_str += '\n<title>' + escape(title) + '</title>'
    item_str += '\n<link>' + link + '</link>'
    item_str += '\n<pubDate>' + pubDate + '</pubDate>'
    item_str += '\n<dc:creator>' + author + '</dc:creator>'
    item_str += '\n<guid isPermaLink="false">https://lolirabbit.wordpress.com/?p=' + str(post_id) + '</guid>'
    item_str += '\n<description>' + description + '</description>'
    item_str += '\n<content:encoded><![CDATA[' + html_content + ']]></content:encoded>'
    item_str += '\n<excerpt:encoded><![CDATA[' + excerpt + ']]></excerpt:encoded>'
    item_str += '\n<wp:post_id>' + str(post_id) + '</wp:post_id>'
    item_str += '\n<wp:post_date>' + post_date + '</wp:post_date>'
    item_str += '\n<wp:post_date_gmt>' + post_date_gmt + '</wp:post_date_gmt>'
    item_str += sample_item_a
    item_str += '\n<wp:post_name>' + permalink + '</wp:post_name>'
    item_str += sample_item_b

    for category in categories:
        quote_category = urllib.parse.quote(category)
        example_category_str = '<category domain="category" nicename="' + quote_category + '"><![CDATA[' + category + ']]></category>'
        item_str += example_category_str

    for tag in tags:
        quote_tag = urllib.parse.quote(tag)
        example_tag_str = '<category domain="post_tag" nicename="' + quote_tag + '"><![CDATA[' + tag + ']]></category>'
        item_str += example_tag_str

    item_str += sample_item_footer
    return item_str


class HelloFrame(wx.Frame):
    def __init__(self, *args, **kw):
        # ensure the parent's __init__ is called
        super(HelloFrame, self).__init__(*args, **kw)

        # self.SetBackgroundColour(wx.Colour(224, 224, 224))

        dsize = wx.DisplaySize()
        self.SetSize(ratioX * dsize[0], ratioY * dsize[1])

        self.Center()

        self.SetToolTip(wx.ToolTip('这是一个框架！'))
        # self.SetCursor(wx.StockCursor(wx.CURSOR_MAGNIFIER))  # 改变鼠标样式

        self.pnl = wx.Panel(self)

        self.export_type = 'Hexo'
        self.display_comments = True  # 是否在博文中显示历史评论

        self.GitHubPathStr = '你的GitHub主文件夹路径'
        self.owner = '你的GitHub账号名'
        self.repo_name = '你存放图片的GitHub库名称'

        self.ratio = 3

        # ================框架================
        self.button1 = wx.Button(self.pnl, wx.ID_ANY, '执行任务')

        self.st11 = wx.StaticText(self.pnl, label='GitHub主文件夹：')
        self.tc11 = wx.TextCtrl(self.pnl, wx.ID_ANY, value=self.GitHubPathStr)

        self.st12 = wx.StaticText(self.pnl, label='GitHub账号名：')
        self.tc12 = wx.TextCtrl(self.pnl, wx.ID_ANY, value=self.owner)

        self.st13 = wx.StaticText(self.pnl, label='GitHub库名称：')
        self.tc13 = wx.TextCtrl(self.pnl, wx.ID_ANY, value=self.repo_name)

        self.st0 = wx.StaticText(self.pnl, label='当前文件夹：')
        # line = str(__file__) + '|' + str(current_dir) + '|' + str(dirpath)
        line = str(current_dir)
        self.tc0 = wx.TextCtrl(self.pnl, wx.ID_ANY, value=line, style=wx.TE_READONLY)

        self.st1 = wx.StaticText(self.pnl, label='读取自：')
        self.tc1 = wx.TextCtrl(self.pnl, wx.ID_ANY, style=wx.TE_READONLY)

        self.st2 = wx.StaticText(self.pnl, label='保存到文件夹：')
        self.tc2 = wx.TextCtrl(self.pnl, wx.ID_ANY, style=wx.TE_READONLY)

        self.st3 = wx.StaticText(self.pnl, label='调试信息：')
        self.tc3 = wx.TextCtrl(self.pnl, wx.ID_ANY, style=wx.TE_READONLY)

        self.st4 = wx.StaticText(self.pnl, label='调试日志：')
        self.tc4 = wx.TextCtrl(self.pnl, wx.ID_ANY, style=wx.TE_MULTILINE | wx.TE_READONLY)

        self.st_progress = wx.StaticText(self.pnl, label='进度：')
        # self.tc5 = wx.TextCtrl(self.pnl, wx.ID_ANY, style=wx.TE_READONLY)
        self.gauge = wx.Gauge(self.pnl, range=100, )  # ,  size=(250, -1)

        self.cb = wx.CheckBox(self.pnl, label='在输出文件中包含评论')
        self.cb.SetValue(self.display_comments)

        self.sampleList = ['Hexo', 'Hugo', 'Jekyll', 'Gridea', 'Wordpress', ]
        self.rbox = wx.RadioBox(self.pnl, -1, "迁移到", (0, 0), wx.DefaultSize,
                                self.sampleList, 5, wx.RA_SPECIFY_COLS)

        # ================尺寸器================
        # self.sBox = wx.BoxSizer()  # 水平尺寸器，不带参数则为默认的水平尺寸器

        self.vBox = wx.BoxSizer(wx.VERTICAL)  # 垂直尺寸器

        # 给尺寸器添加组件，从左往右，从上到下

        self.vBox.Add(self.button1, proportion=1, flag=wx.EXPAND | wx.ALL, border=pad)

        self.vBox.Add(self.rbox, proportion=1, flag=wx.EXPAND | wx.ALL, border=pad)

        self.vBox.Add(self.cb, proportion=1, flag=wx.EXPAND | wx.ALL, border=pad)

        self.sBox11 = wx.BoxSizer()  # 水平尺寸器，不带参数则为默认的水平尺寸器
        self.sBox11.Add(self.st11, proportion=1, flag=wx.EXPAND | wx.ALL, border=pad)
        self.sBox11.Add(self.tc11, proportion=self.ratio, flag=wx.EXPAND | wx.ALL, border=pad)
        self.vBox.Add(self.sBox11, proportion=1, flag=wx.EXPAND | wx.ALL, border=pad)

        self.sBox12 = wx.BoxSizer()  # 水平尺寸器，不带参数则为默认的水平尺寸器
        self.sBox12.Add(self.st12, proportion=1, flag=wx.EXPAND | wx.ALL, border=pad)
        self.sBox12.Add(self.tc12, proportion=self.ratio, flag=wx.EXPAND | wx.ALL, border=pad)
        self.vBox.Add(self.sBox12, proportion=1, flag=wx.EXPAND | wx.ALL, border=pad)

        self.sBox13 = wx.BoxSizer()  # 水平尺寸器，不带参数则为默认的水平尺寸器
        self.sBox13.Add(self.st13, proportion=1, flag=wx.EXPAND | wx.ALL, border=pad)
        self.sBox13.Add(self.tc13, proportion=self.ratio, flag=wx.EXPAND | wx.ALL, border=pad)
        self.vBox.Add(self.sBox13, proportion=1, flag=wx.EXPAND | wx.ALL, border=pad)

        # self.vBox.Add(self.st0, proportion=1, flag=wx.EXPAND | wx.ALL, border=pad)
        # self.vBox.Add(self.tc0, proportion=1, flag=wx.EXPAND | wx.ALL, border=pad)

        self.sBox0 = wx.BoxSizer()  # 水平尺寸器，不带参数则为默认的水平尺寸器
        self.sBox0.Add(self.st0, proportion=1, flag=wx.EXPAND | wx.ALL, border=pad)
        self.sBox0.Add(self.tc0, proportion=self.ratio, flag=wx.EXPAND | wx.ALL, border=pad)
        self.vBox.Add(self.sBox0, proportion=1, flag=wx.EXPAND | wx.ALL, border=pad)

        # self.vBox.Add(self.st1, proportion=1, flag=wx.EXPAND | wx.ALL, border=pad)
        # self.vBox.Add(self.tc1, proportion=1, flag=wx.EXPAND | wx.ALL, border=pad)

        self.sBox1 = wx.BoxSizer()  # 水平尺寸器，不带参数则为默认的水平尺寸器
        self.sBox1.Add(self.st1, proportion=1, flag=wx.EXPAND | wx.ALL, border=pad)
        self.sBox1.Add(self.tc1, proportion=self.ratio, flag=wx.EXPAND | wx.ALL, border=pad)
        self.vBox.Add(self.sBox1, proportion=1, flag=wx.EXPAND | wx.ALL, border=pad)

        # self.vBox.Add(self.st2, proportion=1, flag=wx.EXPAND | wx.ALL, border=pad)
        # self.vBox.Add(self.tc2, proportion=1, flag=wx.EXPAND | wx.ALL, border=pad)

        self.sBox2 = wx.BoxSizer()  # 水平尺寸器，不带参数则为默认的水平尺寸器
        self.sBox2.Add(self.st2, proportion=1, flag=wx.EXPAND | wx.ALL, border=pad)
        self.sBox2.Add(self.tc2, proportion=self.ratio, flag=wx.EXPAND | wx.ALL, border=pad)
        self.vBox.Add(self.sBox2, proportion=1, flag=wx.EXPAND | wx.ALL, border=pad)

        # self.vBox.Add(self.st3, proportion=1, flag=wx.EXPAND | wx.ALL, border=pad)
        # self.vBox.Add(self.tc3, proportion=1, flag=wx.EXPAND | wx.ALL, border=pad)

        self.sBox3 = wx.BoxSizer()  # 水平尺寸器，不带参数则为默认的水平尺寸器
        self.sBox3.Add(self.st3, proportion=1, flag=wx.EXPAND | wx.ALL, border=pad)
        self.sBox3.Add(self.tc3, proportion=self.ratio, flag=wx.EXPAND | wx.ALL, border=pad)
        self.vBox.Add(self.sBox3, proportion=1, flag=wx.EXPAND | wx.ALL, border=pad)

        # self.vBox.Add(self.st4, proportion=1, flag=wx.EXPAND | wx.ALL, border=pad)
        # self.vBox.Add(self.tc4, proportion=self.ratio, flag=wx.EXPAND | wx.ALL, border=pad)

        self.sBox4 = wx.BoxSizer()  # 水平尺寸器，不带参数则为默认的水平尺寸器
        self.sBox4.Add(self.st4, proportion=1, flag=wx.EXPAND | wx.ALL, border=pad)
        self.sBox4.Add(self.tc4, proportion=self.ratio, flag=wx.EXPAND | wx.ALL, border=pad)
        self.vBox.Add(self.sBox4, proportion=self.ratio, flag=wx.EXPAND | wx.ALL, border=pad)

        # self.vBox.Add((0, 30))

        self.sBox5 = wx.BoxSizer()  # 水平尺寸器，不带参数则为默认的水平尺寸器
        self.sBox5.Add(self.st_progress, proportion=1, flag=wx.EXPAND | wx.ALL, border=pad)
        self.sBox5.Add(self.gauge, proportion=self.ratio, flag=wx.EXPAND | wx.ALL, border=pad)
        self.vBox.Add(self.sBox5, proportion=1, flag=wx.EXPAND | wx.ALL, border=pad)

        # self.vBox.Add(self.st_progress, proportion=1, flag=wx.EXPAND | wx.ALL, border=pad)
        # self.vBox.Add(self.gauge, proportion=1, flag=wx.EXPAND | wx.ALL, border=pad)

        # 设置主尺寸
        self.pnl.SetSizer(self.vBox)  # 因为sBox被嵌套在vBox上，所以以vBox为主尺寸

        # ================绑定================
        self.button1.Bind(wx.EVT_BUTTON, self.onStartButton)
        self.rbox.Bind(wx.EVT_RADIOBOX, self.onRadioBox)
        self.cb.Bind(wx.EVT_CHECKBOX, self.onCheck)

        # ================状态栏================
        self.CreateStatusBar()
        self.SetStatusText('准备就绪')

        # ================菜单栏================
        self.fileMenu = wx.Menu()  # 文件菜单

        self.helloItem = self.fileMenu.Append(-1, '你好\tCtrl-H', '程序帮助')
        self.fileMenu.AppendSeparator()
        self.exitItem = self.fileMenu.Append(wx.ID_EXIT, '退出\tCtrl-Q', '退出程序')

        self.helpMenu = wx.Menu()  # 帮助菜单

        self.aboutItem = self.helpMenu.Append(wx.ID_ABOUT, '关于\tCtrl-G', '关于程序')

        self.menuBar = wx.MenuBar()  # 菜单栏
        self.menuBar.Append(self.fileMenu, '文件')
        self.menuBar.Append(self.helpMenu, '其他')

        self.SetMenuBar(self.menuBar)

        # ================绑定================
        self.Bind(wx.EVT_MENU, self.OnHello, self.helloItem)
        self.Bind(wx.EVT_MENU, self.OnExit, self.exitItem)
        self.Bind(wx.EVT_MENU, self.OnAbout, self.aboutItem)

    def get_https_url(self, jpg_url):
        m_server = re.search(p_server, jpg_url)
        jpg_url_https = jpg_url.replace('http://', 'https://', 1)
        jpg_name = Path(jpg_url).name

        if m_server and 'netease.com' in jpg_url:
            server = m_server.group(1)
            # jpg_url = 'http://' + server + '.nosdn.127.net/img/' + jpg_name
            jpg_url_https = 'https://' + server + '.nosdn.127.net/img/' + jpg_name

        # ================图床迁移-GitHub================
        down_jpg_name = jpg_name
        if m_server and not Path(jpg_url).stem.isdigit():
            down_jpg_name = 'img_' + jpg_name
            # print(down_jpg_name)

        self.GitHub = Path(self.GitHubPathStr)
        self.jpg_dir = self.GitHub / self.repo_name
        jpg_path = self.jpg_dir / down_jpg_name
        # print(jpg_path)

        if jpg_path.exists():
            url_segments = [gh_prefix, self.owner, self.repo_name, 'master', down_jpg_name]
            jpg_url_https = 'https://' + '/'.join(url_segments)

        return jpg_url_https

    def markdown_pic(self, match):
        jpg_url = match.group(1)
        jpg_url = jpg_url.split('?')[0]
        jpg_url_https = self.get_https_url(jpg_url)
        string = '\n![](' + jpg_url_https + ')\n'
        return string

    def generate(self, doc, id2name_dict, author, md_dir, output_xml_path, output_txt_path, export_type,
                 display_comments):
        posts = doc['lofterBlogExport']['PostItem']

        if not isinstance(posts, list):
            posts = [posts]

        # posts.reverse()

        output_xml = header + channel_header

        all_pic_urls = []

        for i in range(len(posts)):
            post = posts[i]
            raw_title = post['title']

            # ================标题================
            if isinstance(raw_title, list):  # 长文章
                raw_title = raw_title[0]

            if raw_title:
                title = raw_title
            else:
                title = str(i + 1)

            # ================时间================
            publishTime = post['publishTime']
            modifyTime = publishTime
            if 'modifyTime' in post:
                modifyTime = post['modifyTime']

            publishDate = int2time(publishTime, formatter='%Y-%m-%d')
            publishTime = int2time(publishTime)
            modifyTime = int2time(modifyTime)

            # ================元数据================
            tag = ''
            if 'tag' in post:
                tag = post['tag']

            post_type = post['type']
            permalink = post['permalink']

            categories = [post_type]
            tags = tag.split(',')

            caption = ''
            if 'caption' in post:
                caption = post['caption']

            embed = {}
            if 'embed' in post:
                embed = post['embed']
            if embed != {}:
                embed = json.loads(embed)

            raw_content = ''
            html_full_content = raw_content
            md_content = raw_content

            post_pic_urls = []

            produce = True
            # ================文字================
            if post_type == 'Text':
                if 'content' in post and post['content']:
                    raw_content = post['content']
                md_content = re.sub(p_img, self.markdown_pic, raw_content)
                post_pic_urls = p_ext_img.findall(raw_content)
                # print(post_pic_urls)

            # ================长文章================
            elif post_type == 'Long':
                if 'content' in post and post['content']:
                    raw_content = post['content']
                md_content = re.sub(p_img, self.markdown_pic, raw_content)
                post_pic_urls = p_ext_img.findall(raw_content)
                # print(post_pic_urls)

            # ================问答================
            elif post_type == 'Ask':
                produce = False
            # ================图片================
            elif post_type == 'Photo':
                photoLinks = ''
                if 'photoLinks' in post:
                    photoLinks = post['photoLinks']
                photoLinks = json.loads(photoLinks)  # 将json字符串转换成python对象

                if isinstance(caption, str):
                    md_content = caption

                for photoLink in photoLinks:
                    if 'raw' in photoLink and isinstance(photoLink['raw'], str):
                        jpg_url = photoLink['raw']
                    elif 'orign' in photoLink and isinstance(photoLink['orign'], str):
                        jpg_url = photoLink['orign']
                    else:
                        jpg_url = ''
                        # print(photoLink)
                    if jpg_url != '':
                        jpg_url_https = self.get_https_url(jpg_url)
                        md_content += '\n\n![](' + jpg_url_https + ')'
                        # print(jpg_url_https)
                        post_pic_urls.append(jpg_url_https)
                        # print(post_pic_urls)

            # ================视频================
            elif post_type == 'Video':
                originUrl = embed['originUrl']

                if isinstance(caption, str):
                    md_content = caption

                md_content += '\n\n[' + originUrl + '](' + originUrl + ')'
            # ================音乐================
            elif post_type == 'Music':
                listenUrl = embed['listenUrl']

                song_name = ''
                if 'song_name' in embed:
                    song_name = embed['song_name']

                song_name = song_name.replace('%20', ' ')

                if isinstance(caption, str):
                    md_content = caption

                md_content += '\n\n[' + song_name + '](' + listenUrl + ')'
            # ================如有例外================
            else:
                produce = False

            # html_content = markdown2.markdown(md_content)
            if post_pic_urls:
                all_pic_urls.extend(post_pic_urls)
                # print(post_pic_urls)

            html_content = md_content
            html_content = re.sub('!\[(.*)\]\((.+)\)', r'<img src="\2" alt="\1" />', html_content)  # 图片
            html_content = re.sub('\[(.*)\]\((.+)\)', r'<a href="\2">\1</a>', html_content)  # 链接

            html_content = html_content.strip()

            md_full_content = md_content
            html_full_content = html_content
            if 'commentList' in post and display_comments:
                md_comment_section, html_comment_section = get_comments(post, id2name_dict)
                md_full_content += md_comment_section
                html_full_content += html_comment_section

            num_prefix = str(i + 1).zfill(len(str(len(posts)))) + ' '

            generate_md = True
            if export_type == 'Wordpress':
                generate_md = False

            if export_type == 'Jekyll':
                md_file_stem = publishDate + '-' + safe(title)
            elif export_type == 'Gridea':
                md_file_stem = safe(permalink)
            else:  # if export_type in ['Hexo','Hugo']:
                if raw_title:
                    md_file_stem = num_prefix + safe(raw_title)
                else:
                    md_file_stem = num_prefix + publishTime.replace(':', '-')

            md_file_path = md_dir / (md_file_stem + '.md')

            head_matter = get_head_matter(export_type, title, publishTime, modifyTime, author, categories, tags,
                                          permalink)

            text = head_matter + '\n\n' + md_full_content

            if produce:
                if generate_md:
                    write_text(md_file_path, text)

                if export_type == 'Wordpress':
                    # html_full_content = markdown2.markdown(md_content)
                    item_str = get_item_str(i, title, publishTime, modifyTime, author, categories, tags, permalink,
                                            html_full_content)
                    # print(item_str)
                    output_xml += item_str

            # self.show_label_str(self.tc3, str(md_file_path))

            wx.CallAfter(self.tc3.Clear)
            wx.CallAfter(self.tc3.AppendText, str(md_file_path))

            gau = 100 * (i + 1) / len(posts)
            wx.CallAfter(self.gauge.SetValue, gau)

        output_xml += footer
        if export_type == 'Wordpress':
            write_text(output_xml_path, output_xml)

        all_pic_urls = deduce_list(all_pic_urls)
        all_pic_urls = [x.split('?')[0] for x in all_pic_urls]
        all_pic_urls = [x for x in all_pic_urls if 'raw.githubusercontent.com' not in x]
        output_pictxt = '\r\n'.join(all_pic_urls)
        write_text(output_txt_path, output_pictxt)

        return output_xml

    def process_xmls(self, xmls, export_type, display_comments, event_obj):
        wx.CallAfter(event_obj.Disable)
        start_time = time.time()  # 初始时间戳

        for x in range(len(xmls)):
            xml_file_path = xmls[x]

            # xml_text = open(xml_file_path).read()
            with open(xml_file_path, mode="r", encoding="utf-8") as fp:
                xml_text = fp.read()

            # 处理特殊字符
            xml_text = re.sub(u"[\x00-\x08\x0b-\x0c\x0e-\x1f]+", u"", xml_text)

            doc = xmltodict.parse(xml_text)

            author = '你的lofter昵称'
            m_lofter = re.search(p_lofter, xml_file_path.stem)
            if m_lofter:
                author = m_lofter.group(1)

            md_dir_name = 'markdown-' + export_type + '-' + author

            if export_type == 'Wordpress':
                md_dir = current_dir
            else:
                md_dir = current_dir / md_dir_name
                make_dir(md_dir)

            output_xml_name = export_type + '-' + author + '.xml'
            output_xml_path = current_dir / output_xml_name

            output_txt_name = 'IDM-pictures-' + author + '.txt'
            output_txt_path = current_dir / output_txt_name

            self.show_label_str(self.tc1, str(xml_file_path))
            self.show_label_str(self.tc2, str(md_dir))

            id2name_dict = get_id2name_dict(doc)
            self.generate(doc, id2name_dict, author, md_dir, output_xml_path, output_txt_path, export_type,
                          display_comments)

            # gau = 100 * (x + 1) / len(xmls)
            # wx.CallAfter(self.gauge.SetValue, gau)
        # ================运行时间计时================
        show_run_time = run_time(start_time)
        label_str = '程序结束！' + show_run_time

        self.show_label_str(self.tc3, label_str)

        wx.CallAfter(event_obj.Enable)

    def onStartButton(self, event):
        event_obj = event.GetEventObject()

        self.GitHubPathStr = self.tc11.GetValue()
        self.owner = self.tc12.GetValue()
        self.repo_name = self.tc13.GetValue()

        self.thread_it(self.process_xmls, xmls, self.export_type, self.display_comments, event_obj)
        # event.GetEventObject().Enable()

    def OnExit(self, event):
        self.Close(True)

    def OnHello(self, event):
        wx.MessageBox('来自 wxPython', '你好')

    def OnAbout(self, event):
        wx.MessageBox(message=about_me,
                      caption='关于' + app_name,
                      style=wx.OK | wx.ICON_INFORMATION)

    def onRadioBox(self, event):
        self.export_type = self.rbox.GetStringSelection()

    def onCheck(self, event):
        sender = event.GetEventObject()
        isChecked = sender.GetValue()
        self.display_comments = isChecked

    def show_label_str(self, bar, label_str):
        # print(label_str)

        wx.CallAfter(bar.Clear)
        wx.CallAfter(bar.AppendText, label_str)

        if not label_str.endswith('\n\r'):
            label_str += '\n'

        wx.CallAfter(self.tc4.AppendText, label_str)

    @staticmethod
    def thread_it(func, *args):
        t = threading.Thread(target=func, args=args)
        t.setDaemon(True)  # 守护--就算主界面关闭，线程也会留守后台运行（不对!）
        t.start()  # 启动
        # t.join()          # 阻塞--会卡死界面！


if __name__ == '__main__':
    current_dir = os.path.dirname(os.path.abspath(__file__))
    current_dir = Path(current_dir)

    dirpath = os.getcwd()

    xmls = get_di_xml(current_dir)
    xmls = [x for x in xmls if x.stem.startswith('LOFTER-')]

    app_name = 'Lofter2Hexo v2.28 by 墨问非名'
    about_me = '这是将Lofter导出的xml转换成给静态博客使用的markdown的软件。'

    ratioX = 0.5
    ratioY = 0.7

    pad = 5

    icon_size = (16, 16)

    app = wx.App()

    frm = HelloFrame(None, title=app_name)
    frm.Show()

    ppi_tup = wx.ScreenDC().GetPPI()
    # print(ppi_tup)

    app.MainLoop()
