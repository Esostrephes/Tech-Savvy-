# main.py - Smarta (final) - single-file Kivy/KivyMD app scaffold
import os
import shutil
import json
from datetime import datetime
from kivy.utils import platform
from kivy.uix.filechooser import FileChooserIconView
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.textinput import TextInput
from kivymd.app import MDApp
from kivymd.uix.button import MDRaisedButton, MDFlatButton, MDIconButton
from kivymd.uix.label import MDLabel
from kivymd.uix.textfield import MDTextField
from kivymd.uix.toolbar import MDTopAppBar
from kivymd.uix.snackbar import Snackbar
import requests

# ---------------- Utilities ----------------
def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

def safe_filename(name: str) -> str:
    return "".join(c for c in name if c.isalnum() or c in " _-()").rstrip()

def read_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def write_json(path, data):
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ---------------- Notes Storage ----------------
class NotesStore:
    def __init__(self, base_path):
        self.base = os.path.join(base_path, "notes")
        ensure_dir(self.base)
        self.meta_path = os.path.join(self.base, "metadata.json")
        self.meta = read_json(self.meta_path, {"folders": ["Default"]})
        for f in self.meta["folders"]:
            ensure_dir(os.path.join(self.base, "folders", safe_filename(f)))

    def save_meta(self):
        write_json(self.meta_path, self.meta)

    def list_folders(self):
        return list(self.meta.get("folders", []))

    def create_folder(self, name):
        name = name.strip() or "Unnamed"
        if name in self.meta["folders"]:
            return False
        self.meta["folders"].append(name)
        ensure_dir(os.path.join(self.base, "folders", safe_filename(name)))
        self.save_meta()
        return True

    def rename_folder(self, old, new):
        new = new.strip() or "Unnamed"
        if old not in self.meta["folders"] or new in self.meta["folders"]:
            return False
        idx = self.meta["folders"].index(old)
        self.meta["folders"][idx] = new
        old_path = os.path.join(self.base, "folders", safe_filename(old))
        new_path = os.path.join(self.base, "folders", safe_filename(new))
        if os.path.exists(old_path):
            shutil.move(old_path, new_path)
        else:
            ensure_dir(new_path)
        self.save_meta()
        return True

    def list_notes(self, folder):
        folder_path = os.path.join(self.base, "folders", safe_filename(folder))
        ensure_dir(folder_path)
        notes = []
        for fname in os.listdir(folder_path):
            if fname.endswith(".json"):
                notes.append(fname)
        notes.sort(reverse=True)
        return notes

    def save_note(self, folder, title, body):
        folder_path = os.path.join(self.base, "folders", safe_filename(folder))
        ensure_dir(folder_path)
        note_id = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
        path = os.path.join(folder_path, f"{note_id}.json")
        data = {"id": note_id, "title": title, "body": body, "created": datetime.utcnow().isoformat()}
        write_json(path, data)
        return path

    def load_note(self, folder, note_file):
        path = os.path.join(self.base, "folders", safe_filename(folder), note_file)
        return read_json(path, {})

# ---------------- Communities Storage ----------------
class CommunityStore:
    def __init__(self, base_path):
        self.base = os.path.join(base_path, "communities")
        ensure_dir(self.base)
        self.index_path = os.path.join(self.base, "index.json")
        self.index = read_json(self.index_path, {"communities": []})

    def save_index(self):
        write_json(self.index_path, self.index)

    def list_communities(self):
        return list(self.index.get("communities", []))

    def create_community(self, name):
        name = name.strip() or "Unnamed"
        if name in self.index["communities"]:
            return False
        self.index["communities"].append(name)
        ensure_dir(self.community_path(name))
        write_json(self.posts_path(name), {"posts": []})
        write_json(self.messages_path(name), {"messages": []})
        self.save_index()
        return True

    def community_path(self, name):
        return os.path.join(self.base, safe_filename(name))

    def posts_path(self, name):
        return os.path.join(self.community_path(name), "posts.json")

    def messages_path(self, name):
        return os.path.join(self.community_path(name), "messages.json")

    def attachments_path(self, name):
        p = os.path.join(self.community_path(name), "attachments")
        ensure_dir(p)
        return p

    def add_post(self, community, author, text, attachment_src=None):
        posts = read_json(self.posts_path(community), {"posts": []})
        post_id = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
        attachment_local = None
        if attachment_src:
            att_folder = self.attachments_path(community)
            try:
                base = os.path.basename(attachment_src)
                dest = os.path.join(att_folder, f"{post_id}_{base}")
                shutil.copy2(attachment_src, dest)
                attachment_local = dest
            except Exception:
                attachment_local = None
        post = {"id": post_id, "author": author, "text": text, "attachment": attachment_local, "created": datetime.utcnow().isoformat()}
        posts["posts"].insert(0, post)
        write_json(self.posts_path(community), posts)
        return post

    def list_posts(self, community):
        return read_json(self.posts_path(community), {"posts": []})["posts"]

    def add_message(self, community, sender, text):
        msgs = read_json(self.messages_path(community), {"messages": []})
        msg = {"sender": sender, "text": text, "created": datetime.utcnow().isoformat()}
        msgs["messages"].append(msg)
        write_json(self.messages_path(community), msgs)
        return msg

    def list_messages(self, community):
        return read_json(self.messages_path(community), {"messages": []})["messages"]

# ---------------- UI Widgets ----------------
class HomeWidget(BoxLayout):
    def __init__(self, app, **kwargs):
        super().__init__(orientation='vertical', **kwargs)
        self.app = app
        top_bar = MDTopAppBar(title=app.title)
        top_bar.left_action_items = [["account", lambda x: self.app.switch_screen('profile')]]
        top_bar.right_action_items = [["account-group", lambda x: self.app.switch_screen('community')]]
        self.add_widget(top_bar)

        scroll = ScrollView()
        self.feed_layout = BoxLayout(orientation='vertical', size_hint_y=None, padding=10, spacing=10)
        self.feed_layout.bind(minimum_height=self.feed_layout.setter('height'))
        scroll.add_widget(self.feed_layout)
        self.add_widget(scroll)
        self.reload_suggestions()

        bottom = BoxLayout(size_hint_y=None, height=60, spacing=10, padding=8)
        nav = [ ("home","home"), ("note","notes"), ("robot","ai"), ("account-group","community"), ("account","profile") ]
        for icon, name in nav:
            b = MDIconButton(icon=icon)
            b.bind(on_release=lambda inst, n=name: self.app.switch_screen(n))
            bottom.add_widget(b)
        self.add_widget(bottom)

    def reload_suggestions(self):
        histp = os.path.join(self.app.user_data_dir, "ai_search_history.json")
        hist = read_json(histp, {"history": ["Photosynthesis","Human Anatomy","Nursing Basics"]})["history"]
        self.feed_layout.clear_widgets()
        self.feed_layout.add_widget(MDLabel(text="Suggestions", font_style="H6"))
        for topic in hist:
            btn = MDRaisedButton(text=topic, size_hint_y=None, height=56)
            btn.bind(on_release=lambda inst, t=topic: self.app.open_ai_with_topic(t))
            self.feed_layout.add_widget(btn)

class NotesWidget(BoxLayout):
    def __init__(self, app, notes_store, **kwargs):
        super().__init__(orientation='vertical', **kwargs)
        self.app = app
        self.notes_store = notes_store
        self.current_folder = self.notes_store.list_folders()[0] if self.notes_store.list_folders() else "Default"

        top = BoxLayout(size_hint_y=None, height=56)
        top.add_widget(MDLabel(text="Your Notes", halign='left'))
        folders_btn = MDIconButton(icon='folder')
        folders_btn.bind(on_release=lambda x: self.open_folders_popup())
        top.add_widget(folders_btn)
        self.add_widget(top)

        actions = BoxLayout(size_hint_y=None, height=48, padding=6, spacing=6)
        c = MDRaisedButton(text='Create Note'); c.bind(on_release=lambda x: self.open_create_note())
        i = MDRaisedButton(text='Import Note'); i.bind(on_release=lambda x: self.open_filechooser())
        actions.add_widget(c); actions.add_widget(i)
        self.add_widget(actions)

        self.notes_area = BoxLayout(orientation='vertical', size_hint_y=None, spacing=8, padding=8)
        self.notes_area.bind(minimum_height=self.notes_area.setter('height'))
        scroll = ScrollView(); scroll.add_widget(self.notes_area); self.add_widget(scroll)
        self.folder_label = MDLabel(text=f"Folder: {self.current_folder}", size_hint_y=None, height=30)
        self.add_widget(self.folder_label)

        # load notes
        self.reload_notes()

    def open_folders_popup(self):
        box = BoxLayout(orientation='vertical', spacing=8, padding=8)
        folders = self.notes_store.list_folders()
        for f in folders:
            row = BoxLayout(size_hint_y=None, height=40)
            lbl = MDLabel(text=f, halign='left')
            open_btn = MDRaisedButton(text='Open'); open_btn.bind(on_release=lambda inst, name=f: self.set_current_folder(name))
            rename_btn = MDFlatButton(text='Rename'); rename_btn.bind(on_release=lambda inst, old=f: self.rename_folder_popup(old))
            row.add_widget(lbl); row.add_widget(open_btn); row.add_widget(rename_btn)
            box.add_widget(row)
        create_row = BoxLayout(size_hint_y=None, height=40)
        new_input = TextInput(hint_text='New folder name')
        create_btn = MDRaisedButton(text='Create')
        def do_create(inst):
            created = self.notes_store.create_folder(new_input.text)
            if created:
                Snackbar(text=f"Folder '{new_input.text}' created").open()
                popup.dismiss()
                self.reload_notes()
            else:
                Snackbar(text='Folder exists or invalid').open()
        create_btn.bind(on_release=do_create)
        create_row.add_widget(new_input); create_row.add_widget(create_btn); box.add_widget(create_row)
        popup = Popup(title='Folders', content=box, size_hint=(0.9,0.9)); popup.open()

    def rename_folder_popup(self, old_name):
        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        txt = TextInput(text=old_name)
        btn = MDRaisedButton(text='Rename')
        pop = Popup(title=f'Rename {old_name}', content=content, size_hint=(0.8,0.4))
        def do_rename(inst):
            ok = self.notes_store.rename_folder(old_name, txt.text)
            if ok:
                Snackbar(text='Folder renamed').open()
                pop.dismiss()
                if self.current_folder == old_name:
                    self.set_current_folder(txt.text)
                self.reload_notes()
            else:
                Snackbar(text='Rename failed or name exists').open()
        btn.bind(on_release=do_rename)
        content.add_widget(txt); content.add_widget(btn); pop.open()

    def set_current_folder(self, folder_name):
        self.current_folder = folder_name
        self.folder_label.text = f"Folder: {self.current_folder}"
        self.reload_notes()

    def reload_notes(self):
        self.notes_area.clear_widgets()
        notes = self.notes_store.list_notes(self.current_folder)
        if not notes:
            self.notes_area.add_widget(MDLabel(text='No notes in this folder yet.', size_hint_y=None, height=40))
            return
        for nf in notes:
            data = self.notes_store.load_note(self.current_folder, nf)
            title = data.get('title') or data.get('created') or nf
            snippet = (data.get('body') or '')[:120]
            row = BoxLayout(size_hint_y=None, height=90, padding=6)
            label_box = BoxLayout(orientation='vertical')
            label_box.add_widget(MDLabel(text=title, halign='left'))
            label_box.add_widget(MDLabel(text=snippet, halign='left', theme_text_color='Secondary'))
            open_btn = MDRaisedButton(text='Open', size_hint_x=None, width=80); open_btn.bind(on_release=lambda inst, nf=nf: self.open_note_popup(nf))
            row.add_widget(label_box); row.add_widget(open_btn)
            self.notes_area.add_widget(row)

    def open_note_popup(self, note_file):
        data = self.notes_store.load_note(self.current_folder, note_file)
        content = BoxLayout(orientation='vertical', spacing=8, padding=8)
        title_input = TextInput(text=data.get('title',''), hint_text='Title')
        body_input = TextInput(text=data.get('body',''), hint_text='Body', multiline=True)
        save_btn = MDRaisedButton(text='Save')
        pop = Popup(title='Note', content=content, size_hint=(0.9,0.9))
        def do_save(inst):
            path = os.path.join(self.notes_store.base, 'folders', safe_filename(self.current_folder), note_file)
            data['title'] = title_input.text; data['body'] = body_input.text
            write_json(path, data); pop.dismiss(); self.reload_notes()
        save_btn.bind(on_release=do_save)
        content.add_widget(title_input); content.add_widget(body_input); content.add_widget(save_btn); pop.open()

    def open_create_note(self):
        content = BoxLayout(orientation='vertical', spacing=8, padding=8)
        title_input = TextInput(hint_text='Title'); body_input = TextInput(hint_text='Body', multiline=True)
        save_btn = MDRaisedButton(text='Save')
        pop = Popup(title='Create Note', content=content, size_hint=(0.9,0.9))
        def do_save(inst):
            self.notes_store.save_note(self.current_folder, title_input.text, body_input.text)
            pop.dismiss(); self.reload_notes()
        save_btn.bind(on_release=do_save)
        content.add_widget(title_input); content.add_widget(body_input); content.add_widget(save_btn); pop.open()

    def open_filechooser(self):
        start = '/storage/emulated/0/' if platform == 'android' else os.path.expanduser('~')
        chooser = FileChooserIconView(path=start, filters=['*.txt','*.md'])
        popup = Popup(title='Select file to import', content=chooser, size_hint=(0.95,0.95))
        def on_submit(inst, selection, touch):
            if not selection: popup.dismiss(); return
            src = selection[0]
            try:
                with open(src, 'r', encoding='utf-8') as f:
                    body = f.read()
            except Exception:
                body = ''
            title = os.path.basename(src)
            self.notes_store.save_note(self.current_folder, title, body)
            popup.dismiss(); self.reload_notes(); Snackbar(text=f'Imported {title}').open()
        chooser.bind(on_submit=on_submit); popup.open()

class CommunityWidget(BoxLayout):
    def __init__(self, app, community_store, **kwargs):
        super().__init__(orientation='vertical', **kwargs)
        self.app = app; self.community_store = community_store
        top = MDTopAppBar(title='Communities')
        top.left_action_items = [['plus', lambda x: self.open_create()]]
        self.add_widget(top)
        self.list_area = BoxLayout(orientation='vertical', size_hint_y=None, padding=10, spacing=10)
        self.list_area.bind(minimum_height=self.list_area.setter('height'))
        scroll = ScrollView(); scroll.add_widget(self.list_area); self.add_widget(scroll)
        self.reload_communities()

    def reload_communities(self):
        self.list_area.clear_widgets()
        comms = self.community_store.list_communities()
        if not comms:
            self.list_area.add_widget(MDLabel(text='No communities yet. Create one with +'))
            return
        for c in comms:
            row = BoxLayout(size_hint_y=None, height=100, padding=6)
            left = BoxLayout(orientation='vertical'); left.add_widget(MDLabel(text=c)); left.add_widget(MDLabel(text='Members: local', theme_text_color='Secondary'))
            row.add_widget(left)
            right = BoxLayout(orientation='vertical', size_hint_x=None, width=160)
            join = MDRaisedButton(text='Join'); join.bind(on_release=lambda inst, name=c: self.join_and_open(name))
            view = MDFlatButton(text='View'); view.bind(on_release=lambda inst, name=c: self.open_view(name))
            right.add_widget(join); right.add_widget(view); row.add_widget(right)
            self.list_area.add_widget(row)

    def open_create(self):
        content = BoxLayout(orientation='vertical', spacing=8, padding=8)
        name_in = TextInput(hint_text='Community name'); create_btn = MDRaisedButton(text='Create')
        content.add_widget(name_in); content.add_widget(create_btn)
        pop = Popup(title='Create Community', content=content, size_hint=(0.8,0.4))
        def do_create(inst):
            name = name_in.text.strip()
            if not name: Snackbar(text='Enter a name').open(); return
            ok = self.community_store.create_community(name)
            if ok: Snackbar(text=f"{name} created").open(); pop.dismiss(); self.reload_communities()
            else: Snackbar(text='Already exists').open()
        create_btn.bind(on_release=do_create); pop.open()

    def join_and_open(self, name):
        ensure_dir(self.community_store.community_path(name))
        Snackbar(text=f'Joined {name}').open()
        self.open_view(name)

    def open_view(self, name):
        # View posts, add post with attachment, messages; all stored locally
        box = BoxLayout(orientation='vertical', spacing=8, padding=8)
        box.add_widget(MDLabel(text=f'Community: {name}', font_style='H6', size_hint_y=None, height=36))
        posts_box = BoxLayout(orientation='vertical', size_hint_y=None); posts_box.bind(minimum_height=posts_box.setter('height'))
        posts_scroll = ScrollView(size_hint=(1,0.45)); posts_scroll.add_widget(posts_box); box.add_widget(posts_scroll)
        posts = self.community_store.list_posts(name)
        if not posts: posts_box.add_widget(MDLabel(text='No posts yet', size_hint_y=None, height=30))
        else:
            for p in posts:
                p_row = BoxLayout(size_hint_y=None, height=100, padding=6)
                left = BoxLayout(orientation='vertical')
                left.add_widget(MDLabel(text=f"{p['author']} • {p['created'][:19]}", theme_text_color='Secondary'))
                left.add_widget(MDLabel(text=p.get('text','(no text)'), size_hint_y=None, height=50))
                if p.get('attachment'):
                    left.add_widget(MDLabel(text=f"Attachment: {os.path.basename(p['attachment'])}", theme_text_color='Secondary', size_hint_y=None, height=20))
                p_row.add_widget(left)
                right = BoxLayout(orientation='vertical', size_hint_x=None, width=120)
                share = MDRaisedButton(text='Share'); share.bind(on_release=lambda inst, post=p: self.share_post(post))
                right.add_widget(share); p_row.add_widget(right); posts_box.add_widget(p_row)
        # create post area
        post_input = TextInput(hint_text='Write something...', size_hint_y=None, height=80)
        attach_label = MDLabel(text='No attachment', size_hint_y=None, height=20)
        selected = {'path': None}
        def attach_file(inst):
            start = '/storage/emulated/0/' if platform=='android' else os.path.expanduser('~')
            chooser = FileChooserIconView(path=start)
            pop_att = Popup(title='Select file', content=chooser, size_hint=(0.95,0.95))
            def on_submit(inst2, sel, touch):
                if sel:
                    selected['path'] = sel[0]; attach_label.text = os.path.basename(selected['path'])
                pop_att.dismiss()
            chooser.bind(on_submit=on_submit); pop_att.open()
        attach_btn = MDRaisedButton(text='Attach'); attach_btn.bind(on_release=attach_file)
        post_btn = MDRaisedButton(text='Post')
        def do_post(inst):
            txt = post_input.text.strip(); att = selected['path']
            if not (txt or att): Snackbar(text='Add text or attachment').open(); return
            self.community_store.add_post(name, 'You', txt, att)
            Snackbar(text='Posted').open(); pop.dismiss(); self.open_view(name)
        post_btn.bind(on_release=do_post)
        box.add_widget(post_input)
        box.add_widget(attach_btn); box.add_widget(attach_label); box.add_widget(post_btn)
        # messages
        box.add_widget(MDLabel(text='Community Chat', size_hint_y=None, height=30))
        msgs_box = BoxLayout(orientation='vertical', size_hint_y=None); msgs_box.bind(minimum_height=msgs_box.setter('height'))
        msgs_scroll = ScrollView(size_hint=(1,0.25)); msgs_scroll.add_widget(msgs_box); box.add_widget(msgs_scroll)
        msgs = self.community_store.list_messages(name)
        for m in msgs: msgs_box.add_widget(MDLabel(text=f"{m['sender']}: {m['text']}", size_hint_y=None, height=30))
        msg_input = TextInput(hint_text='Message', multiline=False); send = MDRaisedButton(text='Send')
        def send_msg(inst):
            t = msg_input.text.strip(); 
            if not t: return
            self.community_store.add_message(name, 'You', t)
            Snackbar(text='Message sent').open(); pop.dismiss(); self.open_view(name)
        send.bind(on_release=send_msg)
        box.add_widget(msg_input); box.add_widget(send)
        pop = Popup(title=f'Community: {name}', content=box, size_hint=(0.95,0.95)); pop.open()

    def share_post(self, post):
        # placeholder share: show path and text
        content = BoxLayout(orientation='vertical', spacing=8, padding=8)
        content.add_widget(MDLabel(text='Share (placeholder)'))
        content.add_widget(MDLabel(text=post.get('text',''), size_hint_y=None, height=60))
        if post.get('attachment'): content.add_widget(MDLabel(text=post['attachment'], size_hint_y=None, height=60))
        content.add_widget(MDRaisedButton(text='Close', on_release=lambda x: pop.dismiss()))
        pop = Popup(title='Share', content=content, size_hint=(0.8,0.6)); pop.open()

class ProfileWidget(BoxLayout):
    def __init__(self, app, **kwargs):
        super().__init__(orientation='vertical', **kwargs)
        self.app = app
        self.add_widget(MDTopAppBar(title='Profile'))
        self.add_widget(MDLabel(text='Smarta - profile/settings', halign='left'))
        self.add_widget(MDLabel(text='Theme: Butter (default)', halign='left'))

class SmartaApp(MDApp):
    def build(self):
        self.title = 'Smarta'
        self.theme_cls.primary_palette = 'Amber'
        # user_data_dir: use read-only property, only reference it
        data_dir = self.user_data_dir
        ensure_dir(data_dir)
        self.user_data_dir = data_dir  # safe because we only read and reassign same value locally (works on most platforms)
        self.notes_store = NotesStore(data_dir)
        self.community_store = CommunityStore(data_dir)
        # root layout
        self.root_box = BoxLayout(orientation='vertical')
        self.home_w = HomeWidget(self)
        self.notes_w = NotesWidget(self, self.notes_store)
        self.community_w = CommunityWidget(self, self.community_store)
        self.profile_w = ProfileWidget(self)
        self.ai_w = self.build_ai_widget()
        self.current_widget = None
        self.switch_screen('home')
        return self.root_box

    def build_ai_widget(self):
        box = BoxLayout(orientation='vertical', padding=10, spacing=10)
        box.add_widget(MDTopAppBar(title='AI'))
        self.ai_search = MDTextField(hint_text='Ask AI (summary/detailed)...', size_hint_x=0.95)
        box.add_widget(self.ai_search)
        sb = MDRaisedButton(text='Search'); sb.bind(on_release=lambda x: self.run_search())
        box.add_widget(sb)
        self.ai_results = BoxLayout(orientation='vertical', size_hint_y=None); self.ai_results.bind(minimum_height=self.ai_results.setter('height'))
        scroll = ScrollView(); scroll.add_widget(self.ai_results); box.add_widget(scroll)
        return box

    def run_search(self):
        topic = self.ai_search.text.strip() if hasattr(self, 'ai_search') else ''
        if not topic:
            Snackbar(text='Type a query').open(); return
        # save to history
        histp = os.path.join(self.user_data_dir, 'ai_search_history.json')
        hist = read_json(histp, {'history': []})
        if topic not in hist['history']:
            hist['history'].insert(0, topic); hist['history'] = hist['history'][:50]; write_json(histp, hist)
        # display placeholder summary
        self.ai_results.clear_widgets()
        self.ai_results.add_widget(MDLabel(text=f"Summary for: {topic}\n(Placeholder)", size_hint_y=None, height=120))
        # detailed explanation ad placeholder button
        ad = MDRaisedButton(text='Detailed Explanation (Watch Ad)')
        ad.bind(on_release=lambda x: self.show_ad_placeholder('Watch an ad to unlock detailed explanation (placeholder)'))
        self.ai_results.add_widget(ad)
        # if API key present in config.json, attempt to call OpenAI (user must add key to config)
        cfgp = os.path.join(self.user_data_dir, 'config.json')
        cfg = read_json(cfgp, {})
        api_key = cfg.get('openai_api_key')
        if api_key:
            try:
                # safe minimal request to OpenAI Chat Completions (user supplies key)
                headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
                body = {'model':'gpt-3.5-turbo','messages':[{'role':'user','content':f'Summarize: {topic}'}], 'max_tokens':150}
                resp = requests.post('https://api.openai.com/v1/chat/completions', headers=headers, json=body, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    text = data['choices'][0]['message']['content']
                    self.ai_results.add_widget(MDLabel(text=f"AI: {text}", size_hint_y=None, height=200))
                else:
                    self.ai_results.add_widget(MDLabel(text=f"AI request failed (status {resp.status_code})", size_hint_y=None, height=40))
            except Exception as e:
                self.ai_results.add_widget(MDLabel(text=f"AI request error: {e}", size_hint_y=None, height=40))

    def show_ad_placeholder(self, msg):
        content = BoxLayout(orientation='vertical', spacing=8, padding=8)
        content.add_widget(MDLabel(text=msg))
        close = MDRaisedButton(text='Close', on_release=lambda x: pop.dismiss())
        content.add_widget(close)
        pop = Popup(title='Rewarded Ad (placeholder)', content=content, size_hint=(0.8,0.4)); pop.open()

    def switch_screen(self, name):
        if self.current_widget:
            try: self.root_box.remove_widget(self.current_widget)
            except Exception: pass
        if name == 'home': self.current_widget = self.home_w
        elif name == 'notes': self.notes_w.reload_notes(); self.current_widget = self.notes_w
        elif name == 'ai': self.current_widget = self.ai_w
        elif name == 'community': self.community_w.reload_communities(); self.current_widget = self.community_w
        elif name == 'profile': self.current_widget = self.profile_w
        else: self.current_widget = MDLabel(text=f'Unknown: {name}')
        self.root_box.add_widget(self.current_widget)

if __name__ == '__main__':
    SmartaApp().run()
