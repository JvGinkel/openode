# -*- coding: utf-8 -*-

from random import choice, random, randrange, sample, randint
import requests
from math import ceil
import datetime

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied as OpenodePermissionDenied
from django.core.management.base import NoArgsCommand
from django.db import models
from django.template.defaultfilters import slugify

from openode.const import (
    THREAD_TYPE_DISCUSSION, THREAD_TYPE_QUESTION, NODE_USER_ROLE_MANAGER,
    THREAD_TYPE_DOCUMENT,
    POST_TYPE_THREAD_POST
    )
from openode.const.generator_data import (
    NODE_ANNOTATIONS,
    NODE_TITLES,
    DISCUSSION_TITLES,
    FIRST_NAMES_F,
    FIRST_NAMES_M,
    LAST_NAMES_F,
    LAST_NAMES_M,
    THREAD_CATEGORIES,
    )
# from openode.document.models import Document
from openode.models import (
    Node,
    calculate_gravatar_hash,
    FollowedNode,
    FollowedThread,
    Post,
    Thread,
    )
from openode.models.thread import ThreadCategory
from openode.views.commands import process_vote

from django.conf import settings

################################################################################
################################################################################

USERS_COUNT = getattr(settings, "GENERATOR_USERS_COUNT", 5000)
NODES_COUNT = getattr(settings, "GENERATOR_NODES_COUNT", 1000)
QUESTIONS_COUNT = getattr(settings, "GENERATOR_QUESTIONS_COUNT", 2000)
DISCUSSIONS_COUNT = getattr(settings, "GENERATOR_DISCUSSIONS_COUNT", 2000)
RANDOM_SENTENCES_COUNT = getattr(settings, "GENERATOR_RANDOM_SENTENCES_COUNT", 300)

MAX_POSTS_PER_THREAD = getattr(settings, "GENERATOR_MAX_POSTS_PER_THREAD", 40)
MAX_FOLLOWED_USERS_FOR_THREAD = getattr(settings, "GENERATOR_MAX_FOLLOWED_USERS_FOR_THREAD", 16)
MAX_FOLLOWED_USERS_FOR_NODE = getattr(settings, "GENERATOR_MAX_FOLLOWED_USERS_FOR_NODE", 8)
MAX_COMMENTS_PER_POST = getattr(settings, "GENERATOR_MAX_COMMENTS_PER_POST", 5)
MAX_UP_DOWN_VOTE_FOR_POST = getattr(settings, "GENERATOR_MAX_UP_DOWN_VOTE_FOR_POST", 7)
MAX_NODE_MANAGERS_COUNT = getattr(settings, "GENERATOR_MAX_NODE_MANAGERS_COUNT", 3)
MAX_THREAD_VIEWS = getattr(settings, "GENERATOR_MAX_THREAD_VIEWS", 20000)
MAX_POST_EDITS = getattr(settings, "GENERATOR_MAX_POST_EDITS", 50000)

MAX_DOCUMENTS_PER_NODE = getattr(settings, "GENERATOR_MAX_DOCUMENTS_PER_NODE", 30)
MAX_CATEGORIES_PER_NODE = getattr(settings, "GENERATOR_MAX_CATEGORIES_PER_NODE", 5)

################################################################################
################################################################################


class Command(NoArgsCommand):
    """Django management command class"""

    def handle_noargs(self, **options):
        print "--- DATA GENERATOR START ---"

        Node._meta.get_field("dt_created").auto_now_add = False
        Post._meta.get_field("dt_created").auto_now_add = False
        Thread._meta.get_field("dt_created").auto_now_add = False

        self.random_sentences = []
        self.users_ids = set()
        self.cache = {
            "users": {},
        }

        self.now = datetime.datetime.now()

        # fill user ids
        self.create_users()
        self.users_ids = set(User.objects.values_list("id", flat=True))

        self.gen_random_text()

        if len(self.random_sentences) == 0:
            raise Exception("self.random_sentences is EMPTY")

        commands = [
            self.create_nodes,
            self.create_discussions,
            self.create_questions,
            self.create_documents,
            self.edit_posts,
            self.create_thread_views,
        ]
        for i, command in enumerate(commands, 1):
            print "\n=== Part (%s/%s) started: %s ===" % (i, len(commands), command.__name__)
            command()

        print "--- DATA GENERATOR STOP ---"

    ############################################################################

    def create_nodes(self):
        print "Start creating Nodes"

        j = 0

        for i in xrange(NODES_COUNT):

            title = choice(NODE_TITLES)
            perex = choice(NODE_ANNOTATIONS)

            module_node = self.bool_choice()
            module_qa = self.bool_choice()
            module_forum = self.bool_choice()
            module_library = self.bool_choice()
            module_annotation = self.bool_choice()

            if self.bool_choice(0.9):
                nodes = Node.objects.values_list("id", flat=True).order_by("?")[:1]
                parent_id = nodes[0] if nodes else None
            else:
                # 10% of all created Nodes is root Node
                parent_id = None

            timestamp = self.get_random_datetime(
                from_limit=self.now - datetime.timedelta(days=2 * 365),
                to_limit=self.now - datetime.timedelta(days=7),
            )

            node = Node.objects.create(
                title=title,
                slug=slugify(title),

                parent_id=parent_id,

                perex_node=perex if module_node else "",
                perex_qa=self.get_rand_text(30) if module_qa else "",
                perex_forum=self.get_rand_text(30) if module_forum else "",
                perex_annotation=self.get_rand_text(30) if module_annotation else "",
                perex_library=self.get_rand_text(30) if module_library else "",

                module_qa=module_qa,
                module_forum=module_forum,
                module_library=module_library,
                module_annotation=module_annotation,

                perex_node_important=self.bool_choice() if module_node else False,
                perex_qa_important=self.bool_choice() if module_qa else False,
                perex_forum_important=self.bool_choice() if module_forum else False,
                perex_library_important=self.bool_choice() if module_library else False,
                perex_annotation_important=self.bool_choice() if module_annotation else False,

                dt_created=timestamp,
            )

            # random count of users will follow this node
            if self.bool_choice(0.75):
                for user in self.get_random_users(limit=MAX_FOLLOWED_USERS_FOR_NODE):
                    FollowedNode.objects.get_or_create(node=node, user=user)

            # create managers
            for user in self.get_random_users(limit=MAX_NODE_MANAGERS_COUNT):
                node.node_users.create(
                    user=user,
                    role=NODE_USER_ROLE_MANAGER
                    )

            j += 1

            if j % (NODES_COUNT / 10.0) == 0:
                print j
        print "Node created: %s" % j

        print "Node update_followed_count"
        print "start >>"
        for node in Node.objects.iterator():
            node.update_followed_count()
        print "<< stop"

    ###################################
    ###################################

    def create_questions(self):
        print "--- Start create question ---"
        created_count = self.create_threads(
            THREAD_TYPE_QUESTION,
            QUESTIONS_COUNT,
            comments=True,
            vote=True,
            )
        print "Question created: %s" % created_count

    def create_discussions(self):
        print "--- Start create discussions ---"
        created_count = self.create_threads(
            THREAD_TYPE_DISCUSSION,
            DISCUSSIONS_COUNT
            )
        print "Discussion created: %s" % created_count

    def create_threads(self, thread_type, count, comments=False, vote=False):
        j = 0
        for i in xrange(count):
            user = User.objects.order_by("?")[0]
            node = None
            if thread_type == THREAD_TYPE_QUESTION:
                node = Node.objects.filter(module_qa=True).order_by("?").only("id")[0]
            if thread_type == THREAD_TYPE_DISCUSSION:
                try:
                    node = Node.objects.filter(module_forum=True).exclude(threads__thread_type=THREAD_TYPE_DISCUSSION).order_by("?").only("id")[0]
                except IndexError:
                    print "Could not find proper Node for Discussion"
                    break
            if thread_type == THREAD_TYPE_DOCUMENT:
                node = Node.objects.filter(module_library=True).order_by("?").only("id")[0]

            title = choice(DISCUSSION_TITLES)[:Thread._meta.get_field("title").max_length]

            # create thread and main post
            timestamp = self.get_random_datetime(from_limit=node.dt_created)

            main_post = user.post_thread(
                title=title,
                body_text="<p>%s</p>" % self.get_rand_text(300),
                # tags=tagnames,
                timestamp=timestamp,
                node=node,
                thread_type=thread_type
            )
            thread = main_post.thread

            main_post.dt_created = timestamp
            main_post.dt_changed = timestamp
            main_post.__class__.objects.filter(pk=main_post.pk).update(
                dt_created=main_post.dt_created,
                dt_changed=main_post.dt_changed
                )

            thread.dt_created = timestamp
            thread.dt_changed = timestamp
            thread.__class__.objects.filter(pk=thread.pk).update(
                dt_created=thread.dt_created,
                dt_changed=thread.dt_changed,
                )

            j += 1

            del timestamp

            ###########################
            # CREATE POSTS
            ###########################

            for creator in self.get_random_users(MAX_POSTS_PER_THREAD, exclude_pks=[user.pk]):

                timestamp = self.get_random_datetime(from_limit=thread.dt_created)

                post = creator.post_answer(
                    question=main_post,
                    body_text="<p>%s</p>" % self.get_rand_text(60),
                    timestamp=timestamp,
                )
                post.dt_created = timestamp
                post.dt_changed = timestamp
                post.__class__.objects.filter(pk=post.pk).update(
                    dt_created=post.dt_created,
                    dt_changed=post.dt_changed
                    )

                # up/down vote
                if vote and self.bool_choice(0.25):
                    for user in self.get_random_users(MAX_UP_DOWN_VOTE_FOR_POST, exclude_pks=[creator.pk]):
                        try:
                            process_vote(
                                user=user,
                                post=post,
                                vote_direction=choice(["down", "up", "up", "up"]),  # 75% for up
                            )
                        except OpenodePermissionDenied, e:
                            print e

                # create comment for post
                if comments:
                    if self.bool_choice(0.2):
                        for user in self.get_random_users(MAX_COMMENTS_PER_POST):
                            user.post_comment(
                                parent_post=post,
                                body_text="<p>%s</p>" % self.get_rand_text(20)
                                )

            # accept ansver
            if vote:
                manager_qs = thread.node.node_users.filter(role=NODE_USER_ROLE_MANAGER)[:1]
                if manager_qs:
                    manager = manager_qs[0].user
                    answers = thread.posts.filter(
                        post_type=POST_TYPE_THREAD_POST
                    ).order_by(
                        "-vote_up_count"
                    )[:2]
                    answers = list(answers)
                    if answers:
                        manager.accept_best_answer(choice(answers))

            # follow by users
            # print "follow by users"
            if self.bool_choice(0.3):
                for user in self.get_random_users(MAX_FOLLOWED_USERS_FOR_THREAD):
                    FollowedThread.objects.get_or_create(
                        thread=thread,
                        user=user,
                        defaults={
                            "added_at": self.get_random_datetime(from_limit=thread.dt_created),
                        }
                    )
                thread.update_followed_count()

            if j % (count / 10.0) == 0:
                print j

        return j

    ###################################
    ###################################

    def create_documents(self):
        nodes = Node.objects.filter(module_library=True).order_by("?")[:15]

        # create categories
        for node in nodes:
            for name in sample(THREAD_CATEGORIES, randint(0, MAX_CATEGORIES_PER_NODE)):
                parent = None
                if self.bool_choice(0.5):
                    qs = ThreadCategory.objects.filter(node=node).order_by("?")[:1]
                    if qs:
                        parent = qs[0]
                ThreadCategory.objects.create(
                    node=node,
                    name=name,
                    parent=parent
                )

        # create documents
        for node in nodes:
            for xx in xrange(randint(0, MAX_DOCUMENTS_PER_NODE)):

                user = self.get_random_users(force_amount=1)[0]
                title = self.get_rand_document_title()
                text = "<p>%s</p>" % self.get_rand_text(10)

                category = None
                if self.bool_choice(0.6):
                    qs = ThreadCategory.objects.filter(node=node).order_by("?")[:1]
                    if qs:
                        category = qs[0]

                timestamp = self.get_random_datetime(from_limit=node.dt_created)

                main_post = user.post_thread(
                    title=title,
                    body_text=text,
                    # tags=tagnames,
                    timestamp=timestamp,
                    node=node,
                    thread_type=THREAD_TYPE_DOCUMENT,
                    category=category,
                    external_access=self.bool_choice(0.1),
                )

                thread = main_post.thread

                main_post.dt_created = timestamp
                main_post.dt_changed = timestamp
                main_post.__class__.objects.filter(pk=main_post.pk).update(
                    dt_created=main_post.dt_created,
                    dt_changed=main_post.dt_changed
                    )

                thread.dt_created = timestamp
                thread.dt_changed = timestamp
                thread.__class__.objects.filter(pk=thread.pk).update(
                    dt_created=thread.dt_created,
                    dt_changed=thread.dt_changed,
                    )

        print "Documents created"

    ###################################
    ###################################

    def edit_posts(self):
        print "Start creating PostRevisions"
        j = 0
        for post in Post.objects.order_by("?")[:MAX_POST_EDITS]:
            for user in self.get_random_users(limit=2):
                user.edit_answer(
                    answer=post,
                    body_text="%s %s" % (post.text, self.get_rand_text(20)),
                    revision_comment="",
                    force=True,
                    timestamp=self.get_random_datetime(post.dt_created)
                )
                j += 1
                if j % (MAX_POST_EDITS / 10.0) == 0:
                    print j
        print "Created %s post edit" % j

    ###################################
    ###################################

    def create_thread_views(self):
        """
            create approx. MAX_USERS_PER_THREAD amount of ThreadView
        """
        print "Start creating ThreadViews"
        MAX_USERS_PER_THREAD = 10
        j = 0
        for thread in Thread.objects.order_by("?")[:MAX_THREAD_VIEWS / (MAX_USERS_PER_THREAD / 2)]:
            for user in self.get_random_users(limit=MAX_USERS_PER_THREAD):
                thread.visit(
                    user,
                    force=True,
                    timestamp=self.get_random_datetime(thread.dt_created + datetime.timedelta(days=randint(1, 7)))
                )
                j += 1
                if j % (MAX_THREAD_VIEWS / 10.0) == 0:
                    print j
        print "Created %s ThreadViews" % j

    ###################################
    ###################################

    def create_users(self):
        print "Start create Users"

        j = 0
        for i in xrange(USERS_COUNT):
            email = "openodeuser_%s@coex.cz" % i
            try:
                User.objects.get(models.Q(email=email) | models.Q(username=email))
                continue
            except:
                pass

            f_name, l_name = self.get_random_full_name()

            user = User(
                username=email,
                first_name=f_name,
                last_name=l_name,
                email=email,
                screen_name=" ".join([f_name, l_name]),
            )
            calculate_gravatar_hash(user)
            user.set_password(i)
            user.save()

            j += 1

            if j % (USERS_COUNT / 10.0) == 0:
                print j
        print "Users created: %s" % j

    ############################################################################
    ############################################################################

    def get_random_users(self, limit=1, force_amount=None, exclude_pks=[]):
        if force_amount:
            count = force_amount
        else:
            count = randint(0, limit)

        ids = set(sample(self.users_ids, count))
        ids = ids - set(exclude_pks)

        ret = []
        for _id in ids:
            user = self.cache["users"].get(_id, None)
            if user is None:
                user = User.objects.get(pk=_id)
                self.cache["users"][_id] = user
            ret.append(user)

        return ret

    def get_rand_text(self, max_words, min_words=5):
        """
            @return random text with defined length
            @param max_words - maximum words in result
            @param min_words - minimum words in result
        """

        ret = []
        length = len(ret)
        while max_words > length:
            ret.extend(choice(self.random_sentences).split(" "))
            length = len(ret)
        return " ".join(ret[:randrange(min_words, max_words)])

    def bool_choice(self, probability=0.5):
        """
            @return True with probability 0-100%

            example:
                bool_choice(0.75) return True with 75% probability
        """
        if probability in [0, 0.0]:
            return False
        if probability in [1, 1.0]:
            return True
        return bool(probability > random())

    def get_random_datetime(self, from_limit=None, to_limit=None, default=None):
        """
            @return random datetime timestamp limited by from_limit and to_limit params.
            @param from_limit - datetime or None (now - 365 day will by user)
            @param to_limit - datetime or None (now + 365 day will by user)
        """

        if from_limit is None:
            from_limit = self.now - datetime.timedelta(days=365)

        if to_limit is None:
            to_limit = self.now

        the_now = datetime.datetime.now()

        if not(the_now > to_limit > from_limit):
            if default is None:
                return the_now
            return default

        delta = to_limit - from_limit
        return (from_limit + datetime.timedelta(seconds=randrange((delta.days + 1) * 24 * 60 * 60)))

    def get_rand_document_title(self):
        return choice([
            u"3_PO_PFO_smlouva.doc",
            u"3_Preschool_2012_2013.docx",
            u"11_Pravidla_ZVaS_final.doc",
            u"22_TRB TENDER 2.pdf",
            u"246_smlouva.doc",
            u"2012_hwt_application_form__1_.xlsx",
            u"20120820_lic_smlouva_ml_4_6.rtf",
            u"A120814_AB_ZAKLADNI_PREHLED_ZMEN_MHD.PDF",
            u"anaerobni_lepidla.pdf",
            u"CBRC_Double_Header_Entry_1.docx",
            u"django.pdf",
            u"FSVINT-708-version1-Darsml_fyzos.rtf",
            u"grantova-pravidla.docx",
            u"IMPASOL STRIPPER 100.doc",
            u"IMPASOL STRIPPER 200.doc IMPASOL STRIPPER 300.doc IMPASOL STRIPPER katalog.pdf ",
            u"links.odt ohledani_zemrelych_v_plzenskem_kraji.xlsx Pokyn_dekana_c._1_2012_karierni_rad.docx ",
            u"prilohy_dotace_skolstvi_05_12.xlsx printscreen.png Příloha-C-Smlouvy.docx saiten.xlsx ",
            u"scan1.jpg scan2.jpg seznam.xlsx Seznam-prijemcu_28_3_2012.xlsx small.txt ",
            u"sml-pre.rtf SMS_Gateway.pdf tamilstina.docx tecna.xlsx text_vyzvy_a4_verze_02.pdf ",
            u"ticket-ZD2RLG.pdf tiskopis_navrh_na_lecebne_rehabilitacni_peci_v_olu_dospeli.docx ",
            u"VI Opticke zesilovace navrh kupni smlouvy a dohora o spolupáci na dalších věcech.docx Vypocet_RPSN,.xlsx"
        ])

    def gen_random_text(self):

        MAX_SENTENCES_PER_REQUEST = 100

        _range = int(
            ceil(
                RANDOM_SENTENCES_COUNT / float(MAX_SENTENCES_PER_REQUEST)
            )
        )
        for i in range(_range):
            r = requests.get(
                "http://api.blabot.net",
                params={
                    "scount": MAX_SENTENCES_PER_REQUEST,
                    "method": "list",
                    "dictionary": "3"
                })
            for sentence in r.json()["blabot"]["result"]:
                self.random_sentences.append(sentence)

    def get_random_full_name(self):
        """
            @return tuple of [FirstName, LastName]
        """

        if self.bool_choice():
            # It's a girl, proud father!
            first_names = FIRST_NAMES_F
            last_names = LAST_NAMES_F
        else:
            # It's a boy, proud father!
            first_names = FIRST_NAMES_M
            last_names = LAST_NAMES_M

        return [
            choice(first_names),
            choice(last_names),
        ]
