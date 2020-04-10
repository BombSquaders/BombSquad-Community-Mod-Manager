# ba_meta require api 6
import threading
import json
import weakref
import os
import os.path
import urllib.request
from typing import List
import _ba
import ba
from ba._app import App


# import ba._modutils
SUPPORTS_HTTPS: bool = hasattr(urllib.request, '_have_ssl') and\
    getattr(urllib.request, '_have_ssl')

MOD_PATH: str = App().user_scripts_directory + "/"
BRANCH: str = "rewrite"
USER_REPO: str = "BombSquaders/BombSquad-Community-Mod-Manager"
ENTRY_MOD: str = "modManager"


def index_url():
    """To get the url of the raw json index file"""
    if SUPPORTS_HTTPS:
        yield f"https://raw.githubusercontent.com/{USER_REPO}/{BRANCH}/index.json"
        yield f"https://rawgit.com/{USER_REPO}/{BRANCH}/index.json"
    yield f"http://raw.githack.com/{USER_REPO}/{BRANCH}/index.json"
    yield f"http://rawgit.com/{USER_REPO}/{BRANCH}/index.json"


def mod_url(data):
    """To get url of a mod"""
    if "commit_sha" in data and "filename" in data:
        commit_hexsha = data["commit_sha"]
        filename = data["filename"]
        if SUPPORTS_HTTPS:
            yield f"https://cdn.rawgit.com/{USER_REPO}/{commit_hexsha}/mods/{filename}"
        yield f"http://rawcdn.githack.com/{USER_REPO}/{commit_hexsha}/mods/{filename}"
    if "url" in data:
        if SUPPORTS_HTTPS:
            yield data["url"]
        yield data["url"].replace("https", "http")


def try_fetch_cb(generator, callback):
    """A simple function to try fetch a resource and run callback"""

    def call_back_tfc(data):
        """The function to pass as callback to the thread."""
        if data:
            callback(data)
        else:
            try:
                SimpleGetThread(next(generator), call_back_tfc).start()
            except StopIteration:
                callback(None)

    SimpleGetThread(next(generator), call_back_tfc).start()


class SimpleGetThread(threading.Thread):
    """A simple threading.Thread class to get the data of the resource in background."""
    def __init__(self, url, callback=None):
        threading.Thread.__init__(self)
        self._url = url
        self._callback = callback or (lambda d: None)
        self._context = ba.Context('current')
        activity = ba.getactivity(doraise=False)
        self._activity = weakref.ref(activity) if activity is not None else None

    def _run_callback(self, arg):
        """To run the given callback at time of initialization."""
        # if we were created in an activity context and that activity has since died, do nothing
        # (hmm should we be using a context-call instead of doing this manually?)
        if self._activity is not None and (
                self._activity() is None or self._activity().is_expired()):
            return
        # (technically we could do the same check for session contexts,
        # but not gonna worry about it for now)
        with self._context:
            self._callback(arg)

    def run(self):
        try:
            _ba.set_thread_name("ModManager_SimpleGetThread")
            response = urllib.request.urlopen(urllib.request.Request(self._url, None, {}))
            ba.pushcall(ba.Call(self._run_callback, response.read()), from_other_thread=True)
        except Exception:
            ba.print_exception()
            ba.pushcall(ba.Call(self._run_callback, None), from_other_thread=True)


installed: List[str] = []
installing: List[str] = []


def check_finished():
    """To check if all the mods have finished installing"""
    if any([m not in installed for m in installing]):
        return
    ba.screenmessage("installed everything.")
    if os.path.isfile(MOD_PATH + __name__ + ".pyc"):
        os.remove(MOD_PATH + __name__ + ".pyc")
    if os.path.isfile(MOD_PATH + __name__ + ".py"):
        os.remove(MOD_PATH + __name__ + ".py")
        ba.screenmessage("deleted self")
    ba.screenmessage("activating modManager")
    __import__(ENTRY_MOD)


def install(data, mod):
    """To install a mod from the data."""
    installing.append(mod)
    ba.screenmessage("installing " + str(mod))
    print("installing", mod)
    for dep in data[mod].get("requires", []):
        install(data, dep)
    filename = data[mod]["filename"]

    def call_back(data):
        """A simple callback."""
        if not data:
            ba.screenmessage(f"failed to download mod '{filename}'")
        print("writing", filename)
        with open(MOD_PATH + filename, "w") as file_open:
            file_open.write(str(data))
        installed.append(mod)
        check_finished()

    try_fetch_cb(mod_url(data[mod]), call_back)


def on_index(data):
    """A simple function to receive the index data and start process."""
    if not data:
        ba.screenmessage("network error :(")
        return
    ba.screenmessage("got index data now fetching mods")
    data = json.loads(data)
    install(data["mods"], ENTRY_MOD)

if os.path.exists(MOD_PATH):
    try:
        try_fetch_cb(index_url(), on_index)
    except Exception:
        ba.print_exception()
