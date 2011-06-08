#!/usr/bin/env python
"""
Requires pyaudio and pymad.

pyaudio:
requires portaudio

pymad: http://spacepants.org/src/pymad/download/
requires libmad
"""

import irc
import os.path
import mad
import pyaudio
import random
import time
import threading
import wave
from mutagen.easyid3 import EasyID3

BASE_DIR = '/Volumes/Storage/Music/iTunes/iTunes Media/Music/'

SEARCH_INDEX = None
AUDIO_INDEX = None
AUDIO_THREAD = None
SONG_QUEUE = []
METADATA_INDEX = {}

def build_index():
    global SEARCH_INDEX, AUDIO_INDEX
    
    SEARCH_INDEX = {}
    AUDIO_INDEX = []
    
    start = time.time()

    print "Building audio index"
    
    def append_files(path):
        for fn in os.listdir(path): 
            if fn.startswith('.'):
                continue
            full_path = os.path.join(path, fn)
            if os.path.isdir(full_path):
                append_files(full_path)
            elif fn.endswith('.mp3'):
                metadata = EasyID3(full_path)

                METADATA_INDEX[full_path] = {}
                tokens = []
                for key in ('artist', 'title', 'album'):
                    try:
                        METADATA_INDEX[full_path][key] = unicode(metadata[key][0])
                        tokens.extend(map(lambda x: x.lower(), filter(None, metadata[key][0].split(' '))))
                    except KeyError, e:
                        continue

                AUDIO_INDEX.append(full_path)

                for token in tokens:
                    if token not in SEARCH_INDEX:
                        SEARCH_INDEX[token] = {}
                    if full_path not in SEARCH_INDEX[token]:
                        SEARCH_INDEX[token][full_path] = 1
                    else:
                        SEARCH_INDEX[token][full_path] += 1

    append_files(BASE_DIR)

    print "Done! (%d entries, took %.2fs)" % (len(SEARCH_INDEX), time.time() - start)

build_index()

class PlayAudioThread(threading.Thread):
    def __init__(self, phenny):
        self.phenny = phenny
        self.stopped = False
        self.skipped = False
        super(PlayAudioThread, self).__init__()
        
    def run(self):
        global AUDIO_INDEX, SONG_QUEUE
        
        while not self.stopped:
            if not SONG_QUEUE:
                filename = AUDIO_INDEX[random.randint(0, len(AUDIO_INDEX))]
            else:
                filename = SONG_QUEUE.pop(0)
            self.skipped = False
            self.play_song(filename)

    def play_song(self, filename):
        p = pyaudio.PyAudio()
        bot = self.phenny
        metadata = METADATA_INDEX[filename]

        for channel in bot.config.channels:
            bot.msg(channel, 'Now playing: %s - %s' % (metadata.get('artist'), metadata.get('title')))

        if filename.endswith('.wav'):
            af = wave.open(filename, 'rb')
            rate = af.getframerate()
            channels = af.getnchannels()
            format = p.get_format_from_width(af.getsampwidth())
            audio = 'wav'
        else:
            af = mad.MadFile(filename)
            rate = af.samplerate()
            channels = 2
            format = p.get_format_from_width(pyaudio.paInt32)
            audio = 'mp3'

        # open stream
        stream = p.open(format = format,
                        channels = channels,
                        rate = rate,
                        output = True)

        if audio == 'wav':
            chunk = 1024
            while not (self.stopped or self.skipped):
                data = af.readframes(chunk)
                if not data:
                    self.stopped = True
                    continue
                stream.write(data)
        elif audio == 'mp3':
            while not (self.stopped or self.skipped):
                data = af.read()
                if not data:
                    self.stopped = True
                    continue
                stream.write(data)
            
        stream.close()
        p.terminate()

def f_play(phenny, input): 
    """Plays some music mang."""
    global AUDIO_THREAD, AUDIO_INDEX, SEARCH_INDEX, SONG_QUEUE
     
    # if not input.admin: return

    name = input.group(2)

    if not name: 
        return phenny.reply('What?')

    if name == 'random':
        name = AUDIO_INDEX[random.randint(0, len(AUDIO_INDEX))]

    elif name == 'next':
        if not AUDIO_THREAD:
            AUDIO_THREAD = PlayAudioThread(phenny)
            AUDIO_THREAD.start()
        else:
            AUDIO_THREAD.skipped = True
            AUDIO_THREAD.stopped = False
        return
    
    elif name == 'stop':
        if AUDIO_THREAD:
            AUDIO_THREAD.stopped = True
        return
    
    elif name == 'clear':
        SONG_QUEUE = []
        return phenny.reply('The queue has been cleared.')

    elif name == 'list':
        if not SONG_QUEUE:
            return phenny.reply('There are no songs in the queue.')

        for num, song in enumerate(SONG_QUEUE[:10]):
            metadata = METADATA_INDEX[song]

            phenny.say('%d. %s - %s' % (num, metadata.get('artist'), metadata.get('title')))
        
        return
        # return phenny.reply('Next up: %s - %s' % (metadata.get('artist'), metadata.get('title')))

    elif not os.path.exists(name):
        results = {}
        
        tokens = name.lower().split(' ')
        for token in tokens:
            if token not in SEARCH_INDEX:
                continue
            for full_path, count in SEARCH_INDEX[token].iteritems():
                if full_path not in results:
                    results[full_path] = count
                else:
                    results[full_path] += count
        
        if results:
            name = sorted(results.items(), key=lambda x: -x[1])[0][0]
        else:
            return phenny.reply("Cant find what a song matching your query")
    
    if name:
        if AUDIO_THREAD and not AUDIO_THREAD.stopped:
            metadata = METADATA_INDEX[name]
            phenny.reply("Added %s - %s to the queue" % (metadata.get('artist'), metadata.get('title')))
        SONG_QUEUE.append(name)

    if not AUDIO_THREAD:
        AUDIO_THREAD = PlayAudioThread(phenny)
        AUDIO_THREAD.start()
    else:
        AUDIO_THREAD.stopped = False

f_play.name = 'play'
f_play.example = '.play [Song|stop|next|random]'
f_play.rule = (['play'], r'(.+)')
f_play.priority = 'high'
# f_play.thread = False

def f_reload(phenny, input):
    if AUDIO_THREAD:
        AUDIO_THREAD.stopped = True
        AUDIO_THREAD.join()

    from reload import f_reload
    return f_reload(phenny, input)

f_reload.rule = ('$nick', ['reload'], r'(\S+)?')
f_reload.priority = 'high'

if __name__ == '__main__': 
   print __doc__.strip()
