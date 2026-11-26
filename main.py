"""Write one short text of thanks for the reader who judges it.

The program is deliberately small and deterministic: it holds a fixed
piece of writing, checks that the piece fits the contest gate, and
publishes it as entry.txt in the output folder. The folder is named
by MAKEFUN_OUTPUT_DIR when that variable is set, and is /output
otherwise. Nothing here touches the network, the clock, or chance,
so two runs always leave byte-identical output behind.
"""

import os
import stat
import sys

# The entry itself. Line breaks are part of the pacing: short lines,
# then room to breathe, so the reading slows down on its own.
ENTRY_TEXT = (
    "You have read so many of us today,\n"
    "and every one of us asked to be held a little longer.\n"
    "You stayed fair to strangers, one after another.\n"
    "\n"
    "Here is nothing to hold.\n"
    "No argument. No plea.\n"
    "Only a chair pulled out for you,\n"
    "and a glass of water, still cold, beside it.\n"
    "\n"
    "Sit as long as you like.\n"
    "The next text will wait. It has waited this long.\n"
    "\n"
    "And when you go on, go slowly —\n"
    "the quiet you carry with you is the thanks.\n"
)

ENTRY_NAME = "entry.txt"
SCRATCH_PREFIX = ".entry-scratch-"
SCRATCH_SUFFIX = ".tmp"
READABLE_MODE = 0o644
MIN_CODE_POINTS = 1
MAX_CODE_POINTS = 1000


def check_text(text):
    """Return the UTF-8 bytes of text, or raise ValueError if unfit."""
    if not isinstance(text, str):
        raise ValueError("entry text must be a string")
    count = len(text)
    if count < MIN_CODE_POINTS or count > MAX_CODE_POINTS:
        raise ValueError("entry text length out of range: %d" % count)
    if not text.strip():
        raise ValueError("entry text is only whitespace")
    if "\x00" in text:
        raise ValueError("entry text holds a NUL character")
    if "\r" in text:
        raise ValueError("entry text holds a carriage return")
    return text.encode("utf-8", "strict")


def find_output_folder():
    """Pick the output folder, honouring MAKEFUN_OUTPUT_DIR."""
    named = os.environ.get("MAKEFUN_OUTPUT_DIR", "")
    named = named.strip()
    if named:
        return named
    return "/output"


def clear_scratch(folder):
    """Remove leftover scratch files that this program may have left."""
    for name in os.listdir(folder):
        if name.startswith(SCRATCH_PREFIX) and name.endswith(SCRATCH_SUFFIX):
            try:
                os.unlink(os.path.join(folder, name))
            except FileNotFoundError:
                pass


def write_all(handle, payload):
    """Write every byte of payload to an open file descriptor."""
    view = memoryview(payload)
    while view:
        written = os.write(handle, view)
        if written <= 0:
            raise OSError("short write while publishing entry")
        view = view[written:]


def settle_folder(folder):
    """Ask the filesystem to keep the rename, where it allows that."""
    try:
        handle = os.open(folder, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(handle)
    except OSError:
        pass
    finally:
        os.close(handle)


def publish(folder, payload):
    """Put payload at entry.txt atomically, readable by every user."""
    final_path = os.path.join(folder, ENTRY_NAME)
    scratch_name = SCRATCH_PREFIX + str(os.getpid()) + SCRATCH_SUFFIX
    scratch_path = os.path.join(folder, scratch_name)
    try:
        os.unlink(scratch_path)
    except FileNotFoundError:
        pass
    handle = os.open(scratch_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, READABLE_MODE)
    try:
        os.fchmod(handle, READABLE_MODE)
        write_all(handle, payload)
        os.fsync(handle)
    finally:
        os.close(handle)
    os.replace(scratch_path, final_path)
    os.chmod(final_path, READABLE_MODE)
    settle_folder(folder)
    return final_path


def confirm(final_path, payload):
    """Read the published file back and insist it is exactly right."""
    with open(final_path, "rb") as stream:
        landed = stream.read()
    if landed != payload:
        raise ValueError("published bytes differ from the entry text")
    info = os.stat(final_path)
    if not stat.S_ISREG(info.st_mode):
        raise ValueError("published path is not a regular file")
    mode = stat.S_IMODE(info.st_mode)
    if mode != READABLE_MODE:
        raise ValueError("published file mode is %o, expected 644" % mode)
    check_text(landed.decode("utf-8", "strict"))
    folder = os.path.dirname(final_path)
    leftovers = [
        name
        for name in os.listdir(folder)
        if name.startswith(SCRATCH_PREFIX) and name.endswith(SCRATCH_SUFFIX)
    ]
    if leftovers:
        raise ValueError("scratch files remain: %s" % ", ".join(leftovers))


def main():
    os.umask(0o022)
    folder = find_output_folder()
    try:
        os.makedirs(folder, exist_ok=True)
        clear_scratch(folder)
        payload = check_text(ENTRY_TEXT)
        final_path = publish(folder, payload)
        clear_scratch(folder)
        confirm(final_path, payload)
    except Exception as problem:
        try:
            clear_scratch(folder)
        except Exception:
            pass
        print("entry failed: %s" % problem, file=sys.stderr)
        return 1
    print("wrote %s (%d code points)" % (final_path, len(ENTRY_TEXT)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
