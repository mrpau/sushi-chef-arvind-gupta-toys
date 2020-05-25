#!/usr/bin/env python

import json
import os
import requests
import re
import shutil
import sys

from arvind import ArvindVideo, ArvindLanguage, YOUTUBE_CACHE_DIR, YOUTUBE_ID_REGEX

from bs4 import BeautifulSoup
from bs4.element import NavigableString

from ricecooker.chefs import SushiChef
from ricecooker.classes.files import YouTubeVideoFile
from ricecooker.classes.licenses import get_license
from ricecooker.classes.nodes import VideoNode, TopicNode



ARVIND = "Arvind Gupta Toys"

ARVIND_URL = "http://www.arvindguptatoys.com/films.html"

ROOT_DIR_PATH = os.getcwd()
DOWNLOADS_PATH = os.path.join(ROOT_DIR_PATH, "downloads")
DOWNLOADS_VIDEOS_PATH = os.path.join(DOWNLOADS_PATH, "videos/")

SKIP_VIDEOS_PATH = os.path.join(ROOT_DIR_PATH, "skip_videos.txt")

CACHE_SKIP_VIDEOS_PATH = os.path.join(ROOT_DIR_PATH, "cache_skip_videos.json")

# These are the languages that has no sub topics on its videos.
SINGLE_TOPIC_LANGUAGES = [
    "bhojpuri; bajpuri; bhojapuri",  # actual lang_obj.name in le-utils
    "bhojpuri",                      # future-proofing for upcoming lang_obj.name changes
    "nepali",
    "malayalam",
    "telugu",
    "bengali",
    "odiya",
    "punjabi",
    "marwari; marwadi",     # actual lang_obj.name in le-utils
    "marwari",              # future-proofing for upcoming lang_obj.name changes
    "assamese",
    "urdu",
    "spanish",
    "chinese",
    "indonesian",
    "sci_edu",
    "science/educational",
]

# List of multiple languages on its topics
MULTI_LANGUAGE_TOPIC = ["russian", "french",]

CACHE_SKIP_VIDEO_LIST = []

# This are the estimate total count of arvind gupta toys language contents
TOTAL_ARVIND_LANG = 23

SINGLE_TOPIC = "single"
STANDARD_TOPIC = "standard"
MULTI_LANGUAGE = "multi"

YOUTUBE_DOMAINS = ["youtu.be", "youtube.com"]

# Include this at script argv to delete CACHE_SKIP_VIDEOS_PATH
CLEAR_SKIP_CACHE = "--clear-skip-cache"

DEBUG_MODE = True  # Print extra debug info durig the chef run (disable in prod)



def clean_video_title(title, lang_obj):
    # Remove redundant and misleading words in the video title
    clean_title = title
    try:

        if title != None:
            clean_str = title.replace("-", " ").replace("MB", "").replace("|", "")
            clean_uplang = clean_str.replace(lang_obj.name.upper(), "")
            clean_lowlang = clean_uplang.replace(lang_obj.name.lower(), "")
            clean_caplang = clean_lowlang.replace(lang_obj.name.capitalize() , "")
            clean_format = clean_caplang.replace(".avi", "").replace(".wmv", "").strip()
            clean_extra_spaces = re.sub(" +", " ",clean_format)
            is_int = clean_extra_spaces[-2:]

            if is_int.isdigit():
                clean_extra_spaces = clean_extra_spaces.replace(is_int, "")
            clean_title = clean_extra_spaces
            print("Cleaned video title ====> ", clean_title)
    except Exception as e:
        print('Error cleaning this video title: ', clean_title)

    return clean_title


def load_skip_videos():
    data = []
    if not os.path.exists(CACHE_SKIP_VIDEOS_PATH):
        return data
    with open(CACHE_SKIP_VIDEOS_PATH) as json_file:
        try:
            data = json.load(json_file)
            if type(data) == type([]) :
                return data
        except Exception as e:
            print("Error failed to load cache video", e)
    return data          


def cache_skip_videos():
    global CACHE_SKIP_VIDEO_LIST
    skip_videos = load_skip_videos()
    with open(CACHE_SKIP_VIDEOS_PATH, 'w') as outfile:
        data = CACHE_SKIP_VIDEO_LIST + skip_videos
        json.dump(data, outfile)


def include_video_topic(topic_node, video_data, lang_obj):
    # Include video details to the parent topic node
    video_id = video_data.uid
    video_source_id = 'arvind-video-{0}'.format(video_id)
    video_node = VideoNode(
        source_id=video_source_id, 
        title=clean_video_title(video_data.title, lang_obj), 
        description=video_data.description,
        author=ARVIND,
        thumbnail=video_data.thumbnail,
        license=get_license("CC BY-NC", copyright_holder=ARVIND),
        files=[
            YouTubeVideoFile(
                youtube_id=video_id,
                language=video_data.language,
                high_resolution=False,
            )
        ])
    topic_node.add_child(video_node)


def save_skip_videos(video, topic, lang_obj):
    # Compile skip videos into text file
    if not os.path.exists(SKIP_VIDEOS_PATH):
        open(SKIP_VIDEOS_PATH,"w+")
    text_file = open(SKIP_VIDEOS_PATH, "a")
    video_info = video.language + " - "  + topic + " - " + video.url + " - "  + video.license + "\n" 
    text_file.write(video_info)
    text_file.close()


def download_video_topics(data, topic, topic_node, lang_obj):
    """
    Scrape, collect, and download the videos and their thumbnails.
    """
    global CACHE_SKIP_VIDEO_LIST
    video_source_ids = []
    for vinfo in data[topic]:
        try:
            video_url = vinfo['video_url']
            video = ArvindVideo(
                url=video_url, 
                title=vinfo['video_title'], 
                language=lang_obj.code)

            match = YOUTUBE_ID_REGEX.match(video_url)
            if match:
                youtube_id = match.group('youtube_id')
                skip_videos = load_skip_videos()
                if not youtube_id in skip_videos: 
                    if video.download_info():
                        if video.license_common:
                            video_source_id = 'arvind-video-{0}'.format(video.uid)
                            if video_source_id not in video_source_ids:
                                include_video_topic(topic_node, video, lang_obj)
                                video_source_ids.append(video_source_id)
                            else:
                                print('Skipping duplicate video: ' + str(vinfo['video_url']))
                        else:
                            save_skip_videos(video, topic, lang_obj)
                            CACHE_SKIP_VIDEO_LIST.append(video.uid)
                    else:
                        save_skip_videos(video, topic, lang_obj)
                        CACHE_SKIP_VIDEO_LIST.append(video.uid)

        except Exception as e:
            print('Error downloading this video:', e)


def generate_child_topics(arvind_contents, main_topic, lang_obj, topic_type):
    # Create a topic for each languages
    data = arvind_contents[lang_obj.name]

    for topic_index in data:
        topic_name = topic_index
        if topic_type == STANDARD_TOPIC:
            source_id = 'arvind-child-topic-{0}'.format(topic_name)
            topic_node = TopicNode(title=topic_name, source_id=source_id)
            download_video_topics(data, topic_name, topic_node, lang_obj)
            main_topic.add_child(topic_node)

        if topic_type == SINGLE_TOPIC:
            download_video_topics(data, topic_name, main_topic, lang_obj)
    return main_topic


def create_language_data(lang_data, lang_obj):
    """
    Process the list of elements in `lang_data` to extract video links.
    """
    topic_contents = {}
    initial_topics = []
    prev_topic = ""
    first_count = 1
    total_loop = len(lang_data)

    lang_name = lang_obj.name.lower() 
    for item in lang_data:
        total_loop -= 1

        if isinstance(item, NavigableString) or item.name == 'br':
            continue  # skip whitespace and <br/> tags

        try:
            title = item.text.rstrip().strip()
            video_link = ""
            try:
                video_a_tag = item.find('a')
                if video_a_tag:
                    video_link = video_a_tag.get("href")    # for videos
                else:
                    video_link = ""                         # for headings

                topic_details = {}

                if any(ytd in video_link for ytd in YOUTUBE_DOMAINS):

                    if lang_name in MULTI_LANGUAGE_TOPIC:
                        current_lang = title.split()[0].lower()

                        if first_count == 1:
                            first_count = 0
                            prev_topic = current_lang

                    topic_details['video_url'] = video_link
                    topic_details['video_title'] = title
                    
                    if lang_name in MULTI_LANGUAGE_TOPIC:

                        if prev_topic != current_lang:
                            topic_contents[prev_topic] = initial_topics
                            initial_topics = []
                            prev_topic = current_lang
                    initial_topics.append(topic_details)

            except Exception as e:
                print('>> passing on', e)
                pass

            if first_count == 1:

                if ":" in title:
                    first_count = 0
                    prev_topic = title.replace(":", "").strip()

            if video_link == "":

                if ":" in title:
                    topic_contents[prev_topic] = initial_topics
                    prev_topic = title.replace(":", "").strip()
                    initial_topics = []
        except Exception as e:
            print('>>> passing on', e)
            pass
    
    # This wasn't working (last topic in each standard language was missing) ...
    #       if total_loop == 0:
    #           topic_contents[prev_topic] = initial_topics
    # ... so changed to this:
    topic_contents[prev_topic] = initial_topics
    return topic_contents


def scrape_arvind_page():
    url = ARVIND_URL
    response = requests.get(url)
    page = BeautifulSoup(response.text, 'html5lib')
    content_divs = page.body.div
    list_divs = list(content_divs.children)
    languages_div_start = 5
    languages_list = list(list_divs[languages_div_start].children)
    return languages_list

def get_language_details(lang_name):
    video_lang = ArvindLanguage(name=lang_name)

    if video_lang.get_lang_obj():
        return video_lang
    return None

def create_language_topic():
    arvind_languages = scrape_arvind_page()
    main_topic_list = []

    if os.path.exists(SKIP_VIDEOS_PATH):
        os.remove(SKIP_VIDEOS_PATH)
    loop_max = TOTAL_ARVIND_LANG
    language_next_int = 7
    loop_couter = 0
    while (loop_couter != loop_max):
        try:
            lang_name = arvind_languages[language_next_int].get('id')
            lang_obj = get_language_details(lang_name.lower())

            if lang_obj != None:
                lang_name = lang_obj.name
                lang_name_lower = lang_name.lower()
                print('== Processing ', lang_name, '='*60)
                language_source_id = 'arvind-parent-topic-{0}'.format(lang_name_lower)
                # print('language_source_id =', language_source_id)
                get_language_data = list(arvind_languages[language_next_int])
                # print('len(get_language_data) = ', len(get_language_data))
                data_contents = { lang_name: create_language_data(get_language_data, lang_obj) }
                # print('len(data_contents[lang_name])', len(data_contents[lang_name]))
                language_topic = TopicNode(title=lang_name.capitalize(), source_id=language_source_id)

                if lang_name_lower not in SINGLE_TOPIC_LANGUAGES and lang_name_lower not in MULTI_LANGUAGE_TOPIC:
                    print("=======> This Language is in standard format", lang_name)
                    topic_type = STANDARD_TOPIC
                    generate_child_topics(data_contents, language_topic, lang_obj, topic_type)
                    main_topic_list.append(language_topic)
                    print("=====>finished", lang_name)

                if lang_name_lower in SINGLE_TOPIC_LANGUAGES:
                    print("=====> This Language is in single topic format ", lang_name)
                    topic_type = SINGLE_TOPIC
                    generate_child_topics(data_contents, language_topic, lang_obj, topic_type)
                    main_topic_list.append(language_topic)
                    print("=====>finished", lang_name)

                if lang_name_lower in MULTI_LANGUAGE_TOPIC:
                    print("=====> This Language is in multiple langauage topic format ", lang_name)
                    lang_data = create_language_data(get_language_data, lang_obj)
                    for lang in lang_data:
                        current_lang = get_language_details(lang.lower())
                        if current_lang != None:
                            parent_source_id = 'arvind-parent-topic-{0}'.format(current_lang.name)
                            parent_topic = TopicNode(title=lang.capitalize(), source_id=parent_source_id)
                            data_dic = {current_lang.name: {"": lang_data[lang]}}
                            topic_type = SINGLE_TOPIC
                            generate_child_topics(data_dic, parent_topic, current_lang, topic_type)
                            main_topic_list.append(parent_topic)
                            print("=====>finished ", lang)

        except Exception as e:
            print("===> error getting language topics: ", e)
            # raise(e)

        language_next_int += 4
        loop_couter += 1

    cache_skip_videos()
    return main_topic_list


class ArvindChef(SushiChef):
    channel_info = {
        "CHANNEL_TITLE": "Arvind Gupta Toys",
        "CHANNEL_SOURCE_DOMAIN": "arvindguptatoys.com",
        "CHANNEL_SOURCE_ID": "toys-from-trash",
        "CHANNEL_LANGUAGE": "mul",
        "CHANNEL_THUMBNAIL": 'chefdata/arvind_gupta_thumbnail.png',
        "CHANNEL_DESCRIPTION": "Math and science activities through low-cost " \
                "materials all in the form of videos to provide various pathways for children to explore" \
                " and deepen their understanding of concepts in low-resource contexts around the world." \
                " Valuable resource library for teachers to incorporate in their lessons, for parents to" \
                " work with children at home using readily available, simple, and low-cost materials.",
    }

    def pre_run(self, args, options):
        """This function will get called by ricecooker before the chef runs."""
        if args['update']:
            # delete video info .json files cached in chefdata/youtubecache/
            print('Deleting vinfo .json files in {}'.format(YOUTUBE_CACHE_DIR))
            if os.path.exists(YOUTUBE_CACHE_DIR):
                shutil.rmtree(YOUTUBE_CACHE_DIR)
            os.makedirs(YOUTUBE_CACHE_DIR)

    def construct_channel(self, **kwargs):

        channel = self.get_channel(**kwargs)

        languages_topic = create_language_topic()
        for lang_topic in languages_topic:
            channel.add_child(lang_topic)
        return channel


def check_arg():
    """Remove cache skip videos if CLEAR_SKIP_CACHE in argv"""
    args_val = sys.argv
    if CLEAR_SKIP_CACHE in args_val:
        args_val.remove(CLEAR_SKIP_CACHE)
        if os.path.exists(CACHE_SKIP_VIDEOS_PATH):
            os.remove(CACHE_SKIP_VIDEOS_PATH)


if __name__ == "__main__":
    """
    Run this script on the command line using:
        python sushichef.py -v --reset --token=YOURTOKENHERE9139139f3a23232
    """
    check_arg()
    chef = ArvindChef()
    chef.main()
