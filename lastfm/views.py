# -*- encoding: utf-8 -*-
import urllib2, time, re
from hashlib import md5
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render_to_response
from libs.util import render_as_text, render_as_json
import simplejson as json
from lxml import etree
from other.models import ListeningHistory

def handshake(lastfm_login, lastfm_session):
    # теперь пожмем ручки
    nowtime = str(int(time.time()))
    handtoken = md5(settings.LASTFM_SECRET + str(nowtime)).hexdigest()
    handget = 'hs=true&p=1.2.1&c=tst&v=1.0&u=' + lastfm_login + '&t=' + str(nowtime) + '&a=' + handtoken + '&api_key=' + settings.LASTFM_KEY + '&sk=' + lastfm_session
    answer = urllib2.urlopen("http://post.audioscrobbler.com/?%s" % handget).read()
    session =  answer.split("\n")[1]
    return session

def callback(request):
    token = request.GET.get("token", "")
    if not token: return HttpResponse("Bad hash")

    # получим себе key
    api_sig = md5('api_key' + settings.LASTFM_KEY + 'methodauth.getSessiontoken' + token + settings.LASTFM_SECRET).hexdigest()
    get = 'method=auth.getSession&api_key=' + settings.LASTFM_KEY + '&token=' + token + '&api_sig=' + api_sig
    answer = urllib2.urlopen("http://ws.audioscrobbler.com/2.0/?%s" % get).read().replace("\n", "")
    lastfm_login = re.search("<name>(.*?)</name>", answer).group(1)
    lastfm_session =  re.search("<key>(.*?)</key>", answer).group(1)

    session = handshake(lastfm_login, lastfm_session)

    # и куки не забудем
    response = render_to_response("static/lastfmok.html")
    response.set_cookie("lastfm_session", session, max_age=365*24*60*60)
    response.set_cookie("lastfm_session_key", lastfm_session, max_age=365*24*60*60)
    response.set_cookie("lastfm_login", lastfm_login, max_age=365*24*60*60)

    return response

@render_as_text
def nowplaying(request):
    nowtime = int(time.time())
    lastfm_session = request.COOKIES.get("lastfm_session", "")
    lastfm_session_key = request.COOKIES.get("lastfm_session_key", "")
    lastfm_login = request.COOKIES.get("lastfm_login", "")
    artist = urllib2.quote(request.POST.get("artist", "Unknown Artist").encode("utf-8", "ignore").replace("&#39;", "\'"))
    duration = urllib2.quote(request.POST.get("duration_ms", "360").encode("utf-8", "ignore"))
    song = urllib2.quote(request.POST.get("title", "Track 1").encode("utf-8", "ignore").replace("&#39;", "\'"))

    url = "http://post2.audioscrobbler.com:80/np_1.2"
    req = urllib2.Request(url, u's=' + lastfm_session + '&a=' + artist + '&t=' + song + '&b=&l=' + duration + '&n=&m=')
    response = HttpResponse()
    try:
        data = urllib2.urlopen(req).read().strip()
        if data == "BADSESSION":
            lastfm_session = handshake(lastfm_login, lastfm_session_key)
            response.set_cookie("lastfm_session", lastfm_session, max_age=365*24*60*60)
            req = urllib2.Request(url, u's=' + lastfm_session + '&a=' + artist + '&t=' + song + '&b=&l=' + duration + '&n=&m=')
            data = urllib2.urlopen(req).read().strip()
            ans = "%s %s" % (data, "SECOND")
        else:
            ans = "%s %s" % (data, "FIRST")
        response.content = "%s %s" % (lastfm_session, ans)
    except:
        response.content = "FAIL"
    return response

def scrobble(request):
    nowtime = str(int(time.time()))
    lastfm_session = request.COOKIES.get("lastfm_session", "")
    lastfm_session_key = request.COOKIES.get("lastfm_session_key", "")
    lastfm_login = request.COOKIES.get("lastfm_login", "")
    artist = urllib2.quote(request.POST.get("artist", "Unknown Artist").encode("utf-8", "ignore").replace("&#39;", "\'"))
    duration = urllib2.quote(request.POST.get("duration_ms", "360").encode("utf-8", "ignore"))
    song = urllib2.quote(request.POST.get("title", "Track 1").encode("utf-8", "ignore").replace("&#39;", "\'"))

    url = "http://post2.audioscrobbler.com:80/protocol_1.2"
    req = urllib2.Request(url, u's=' + lastfm_session + '&a[0]=' + artist + '&t[0]=' + song + '&i[0]=' + str(nowtime) + '&o[0]=P&r[0]=&l[0]=' + duration + '&b[0]=&n[0]=&m[0]=')
    response = HttpResponse()
    try:
        data = urllib2.urlopen(req).read().strip()
        if data == "BADSESSION":
            lastfm_session = handshake(lastfm_login, lastfm_session_key)
            response.set_cookie("lastfm_session", lastfm_session, max_age=365*24*60*60)
            req = urllib2.Request(url, u's=' + lastfm_session + '&a[0]=' + artist + '&t[0]=' + song + '&i[0]=' + str(nowtime) + '&o[0]=P&r[0]=&l[0]=' + duration + '&b[0]=&n[0]=&m[0]=')
            data = urllib2.urlopen(req).read().strip()
            ans = "%s %s" % (data, "SECOND")
        else:
            ans = "%s %s" % (data, "FIRST")
        response.content = "%s %s" % (lastfm_session, ans)
    except:
        response.content = "FAIL"
    return response

@render_as_json
def getartistinfo(request):
    try:
        track = json.loads(request.POST.get("track").encode("utf-8", "ignore"))
        artist = track["artist"].encode("utf-8", "ignore")
    except:
        return { "status": "NeOK", "message": "Fail! No track" }

    try:
        history_track = ListeningHistory.objects.create(user=request.user, track_artist=track["artist"],
                                                        track_title=track["title"], track_id=track["id"])
        history_track.save()
    except Exception, e:
        return { "status": "NeOK", "message": u"Ошибка сохранения трека: %s" % e }

    try:
        if not artist: raise Exception(u"No artist")
        url = u"http://ws.audioscrobbler.com/2.0/?method=artist.getinfo&lang=ru&autocorrect=1&api_key=%s&artist=%s" % (settings.LASTFM_KEY, urllib2.quote(artist))
        tree = etree.fromstring(urllib2.urlopen(url).read())
        if not tree: raise Exception(u"No info")
        tree = tree.find("artist")
        answer = {
            "name": tree.find("name").text,
            "url": tree.find("url").text,
            "image": [img.text for img in tree.findall("image")],
            "similar": [art.find("name").text for art in tree.find("similar").findall("artist")],
            "bio": tree.find("bio").find("summary").text
        }
        return { "status": "OK", "artist": answer }
    except Exception, e:
        return { "status": "NeOK", "message": "Fail! %s" % e }

@render_as_json
def getrecommended(request):
    lastfm_session_key = request.COOKIES.get("lastfm_session_key", "")
    try:
        api_sig = md5(u"api_key%smethoduser.getRecommendedArtistssk%s%s" % (settings.LASTFM_KEY, lastfm_session_key, settings.LASTFM_SECRET)).hexdigest()
        url = u"http://ws.audioscrobbler.com/2.0/?api_key=%s&method=user.getRecommendedArtists&sk=%s&api_sig=%s" % (settings.LASTFM_KEY, lastfm_session_key, api_sig)
        tree = etree.fromstring(urllib2.urlopen(url).read())
        if not tree: raise Exception(u"No info")
        tree = tree.find("recommendations")
        recommendations = []
        for artist in tree.findall("artist"):
            recommendations.append(artist.find("name").text)
        return { "status": "OK", "artists": recommendations }
    except Exception, e:
        return { "status": "NeOK", "message": "Fail! %s" % e }