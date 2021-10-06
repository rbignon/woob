# -*- coding: utf-8 -*-

# Copyright(C) 2013 Julien Veyssier
#
# This file is part of a woob module.
#
# This woob module is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This woob module is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this woob module. If not, see <https://www.gnu.org/licenses/>.

from __future__ import unicode_literals

import re

from woob.browser import PagesBrowser, URL
from woob.browser.profiles import Wget
from woob.capabilities.base import NotAvailable, NotLoaded
from woob.capabilities.cinema import Movie, Person
from woob.tools.compat import unicode, html_unescape

from .pages import PersonPage, MovieCrewPage, BiographyPage,  ReleasePage

from datetime import datetime

__all__ = ['ImdbBrowser']


class ImdbBrowser(PagesBrowser):
    BASEURL = 'https://www.imdb.com'
    PROFILE = Wget()

    movie_crew = URL(r'/title/(?P<id>tt[0-9]*)/fullcredits.*', MovieCrewPage)
    release = URL(r'/title/(?P<id>tt[0-9]*)/releaseinfo.*', ReleasePage)
    bio = URL(r'/name/(?P<id>nm[0-9]*)/bio.*', BiographyPage)
    person = URL(r'/name/(?P<id>nm[0-9]*)/*', PersonPage)

    def iter_movies(self, pattern):
        res = self.open(f'https://v2.sg.media-imdb.com/suggestion/titles/{pattern[0]}/{pattern}.json')
        jres = res.json()

        for m in jres['d']:
            movie = Movie(m['id'], m['l'])
            movie.other_titles = NotLoaded
            movie.release_date = NotLoaded
            movie.duration = NotLoaded
            movie.short_description = NotLoaded
            movie.pitch = NotLoaded
            movie.country = NotLoaded
            movie.note = NotLoaded
            movie.roles = NotLoaded
            movie.all_release_dates = NotLoaded
            movie.thumbnail_url = m['i']['imageUrl']
            yield movie

    def iter_persons(self, pattern):
        res = self.open(f'https://v2.sg.media-imdb.com/suggestion/names/{pattern[0]}/{pattern}.json')
        jres = res.json()

        for p in jres['d']:
            person = Person(p['id'], p['l'])
            person.real_name = NotLoaded
            person.birth_place = NotLoaded
            person.birth_date = NotLoaded
            person.death_date = NotLoaded
            person.gender = NotLoaded
            person.nationality = NotLoaded
            person.short_biography = NotLoaded
            person.short_description = NotLoaded
            person.roles = NotLoaded
            if 'i' in p:
                person.thumbnail_url = p['i']['imageUrl']
            yield person

    def get_movie(self, id):
        res = self.open(f'https://www.omdbapi.com/?apikey=b7c56eb5&i={id}&plot=full')
        if res is not None:
            jres = res.json()
        else:
            return None

        title = NotAvailable
        duration = NotAvailable
        release_date = NotAvailable
        pitch = NotAvailable
        country = NotAvailable
        note = NotAvailable
        short_description = NotAvailable
        thumbnail_url = NotAvailable
        other_titles = []
        genres = []
        roles = {}

        if 'Title' not in jres:
            return
        title = html_unescape(unicode(jres['Title'].strip()))
        if 'Poster' in jres:
            thumbnail_url = unicode(jres['Poster'])
        if 'Director' in jres:
            short_description = unicode(jres['Director'])
        if 'Genre' in jres:
            for g in jres['Genre'].split(', '):
                genres.append(g)
        if 'Runtime' in jres:
            m = re.search('(\d+?) min', jres['Runtime'])
            if m:
                duration = int(m.group(1))
        if 'Released' in jres:
            released_string = str(jres['Released'])
            if released_string == 'N/A':
                release_date = NotAvailable
            else:
                months = {
                        'Jan':'01',
                        'Feb':'02',
                        'Mar':'03',
                        'Apr':'04',
                        'May':'05',
                        'Jun':'06',
                        'Jul':'07',
                        'Aug':'08',
                        'Sep':'09',
                        'Oct':'10',
                        'Nov':'11',
                        'Dec':'12',
                         }
                for st in months:
                    released_string = released_string.replace(st,months[st])
                release_date = datetime.strptime(released_string, '%d %m %Y')
        if 'Country' in jres:
            country = u''
            for c in jres['Country'].split(', '):
                country += f'{c}, '
            country = country[:-2]
        if 'Plot' in jres:
            pitch = unicode(jres['Plot'])
        if 'imdbRating' in jres and 'imdbVotes' in jres:
            note = f'{jres["imdbRating"]}/10 ({jres["imdbVotes"]} votes)'
        for r in ['Actors', 'Director', 'Writer']:
            if f'{r}' in jres.keys():
                roles[f'{r}'] = [('N/A',e) for e in jres[f'{r}'].split(', ')]

        movie = Movie(id, title)
        movie.other_titles = other_titles
        movie.release_date = release_date
        movie.duration = duration
        movie.genres = genres
        movie.pitch = pitch
        movie.country = country
        movie.note = note
        movie.roles = roles
        movie.short_description = short_description
        movie.all_release_dates = NotLoaded
        movie.thumbnail_url = thumbnail_url
        return movie

    def get_person(self, id):
        self.person.go(id=id)
        assert self.person.is_here()
        return self.page.get_person(id)

    def get_person_biography(self, id):
        self.bio.go(id=id)
        assert self.bio.is_here()
        return self.page.get_biography()

    def iter_movie_persons(self, movie_id, role):
        self.movie_crew.go(id=movie_id)
        assert self.movie_crew.is_here()
        for p in self.page.iter_persons(role):
            yield p

    def iter_person_movies(self, person_id, role):
        self.person.go(id=person_id)
        assert self.person.is_here()
        return self.page.iter_movies(role)

    def iter_person_movies_ids(self, person_id):
        self.person.go(id=person_id)
        assert self.person.is_here()
        for movie in self.page.iter_movies_ids():
            yield movie

    def iter_movie_persons_ids(self, movie_id):
        self.movie_crew.go(id=movie_id)
        assert self.movie_crew.is_here()
        for person in self.page.iter_persons_ids():
            yield person

    def get_movie_releases(self, id, country):
        self.release.go(id=id)
        assert self.release.is_here()
        return self.page.get_movie_releases(country)
