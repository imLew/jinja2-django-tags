# coding: utf-8
from __future__ import unicode_literals

import datetime

from django.test import SimpleTestCase, override_settings
from django.test.utils import requires_tz_support
from django.utils import timezone, translation
from jinja2 import Environment, TemplateSyntaxError
from jinja2.ext import Extension

from jdj_tags.extensions import (DjangoCompat, DjangoCsrf, DjangoI18n, DjangoL10n, DjangoNow,
                                 DjangoStatic, DjangoUrl)

try:
    from unittest import mock
except ImportError:
    import mock


class DjangoCsrfTest(SimpleTestCase):
    def setUp(self):
        self.env = Environment(extensions=[DjangoCsrf])
        self.template = self.env.from_string("{% csrf_token %}")

    def test_token(self):
        context = {'csrf_token': 'a_csrf_token'}
        expected = '<input type="hidden" name="csrfmiddlewaretoken" value="a_csrf_token" />'

        self.assertEqual(expected, self.template.render(context))

    def test_empty_token(self):
        context1 = {}
        context2 = {'csrf_token': 'NOTPROVIDED'}

        self.assertEqual('', self.template.render(context1))
        self.assertEqual('', self.template.render(context2))


class DjangoI18nTestBase(SimpleTestCase):
    @staticmethod
    def _gettext(message):
        return '{} - translated'.format(message)

    @staticmethod
    def _pgettext(context, message):
        return 'alt translated'

    @staticmethod
    def _ngettext(singular, plural, number):
        return 'count translated'

    @staticmethod
    def _npgettext(context, singular, plural, number):
        return 'count alt translated'

    def setUp(self):
        gettext_patcher = mock.patch('jdj_tags.extensions.gettext', side_effect=self._gettext)
        pgettext_patcher = mock.patch('jdj_tags.extensions.pgettext', side_effect=self._pgettext)
        ngettext_patcher = mock.patch('jdj_tags.extensions.ngettext', side_effect=self._ngettext)
        npgettext_patcher = mock.patch('jdj_tags.extensions.npgettext', side_effect=self._npgettext)

        self.gettext = gettext_patcher.start()
        self.pgettext = pgettext_patcher.start()
        self.ngettext = ngettext_patcher.start()
        self.npgettext = npgettext_patcher.start()

        self.addCleanup(gettext_patcher.stop)
        self.addCleanup(pgettext_patcher.stop)
        self.addCleanup(ngettext_patcher.stop)
        self.addCleanup(npgettext_patcher.stop)

        self.env = Environment(extensions=[DjangoI18n])


class DjangoI18nTransTest(DjangoI18nTestBase):
    def test_simple_trans(self):
        template1 = self.env.from_string("{% trans 'Hello World' %}")
        template2 = self.env.from_string(
            "{% trans 'Hello World' context 'some context' %}"
        )
        template3 = self.env.from_string("{{ _('Hello World') }}")
        template4 = self.env.from_string("{{ gettext('Hello World') }}")
        template5 = self.env.from_string("{{ pgettext('some context', 'Hello World') }}")

        self.assertEqual('Hello World - translated', template1.render())
        self.gettext.assert_called_with('Hello World')
        self.assertEqual('alt translated', template2.render())
        self.pgettext.assert_called_with('some context', 'Hello World')
        self.assertEqual('Hello World - translated', template3.render())
        self.gettext.assert_called_with('Hello World')
        self.assertEqual('Hello World - translated', template4.render())
        self.gettext.assert_called_with('Hello World')
        self.assertEqual('alt translated', template5.render())
        self.pgettext.assert_called_with('some context', 'Hello World')

    def test_noop(self):
        template = self.env.from_string("{% trans 'Hello World' noop %}")

        self.assertEqual('Hello World', template.render())
        self.gettext.assert_not_called()

    def test_as_var(self):
        template = self.env.from_string(
            "{% trans 'Hello World' as myvar %}My var is: {{ myvar }}!"
        )

        self.assertEqual('My var is: Hello World - translated!', template.render())
        self.gettext.assert_called_with('Hello World')

    def test_noop_as_var(self):
        template1 = self.env.from_string(
            "{% trans 'Hello World' noop as myvar %}My var is: {{ myvar }}!"
        )
        template2 = self.env.from_string(
            "{% trans 'Hello World' as myvar noop %}My var is: {{ myvar }}!"
        )

        expected_str = 'My var is: Hello World!'

        self.assertEqual(expected_str, template1.render())
        self.gettext.assert_not_called()
        self.assertEqual(expected_str, template2.render())
        self.gettext.assert_not_called()

    def test_errors(self):
        template1 = "{% trans 'Hello World' foo %}"
        template2 = "{% trans 'Hello World' noop context 'some context' %}"
        template3 = "{% trans 'Hello World' context 'some context' noop %}"

        error_messages = [
            (template1, "expected 'noop', 'context' or 'as'"),
            (template2, "noop translation can't have context"),
            (template3, "noop translation can't have context"),
        ]

        for template, msg in error_messages:
            with self.assertRaisesMessage(TemplateSyntaxError, msg):
                self.env.from_string(template)


class DjangoI18nBlocktransTest(DjangoI18nTestBase):
    def test_simple(self):
        template1 = self.env.from_string('{% blocktrans %}Translate me!{% endblocktrans %}')
        template2 = self.env.from_string(
            "{% blocktrans context 'foo' %}Translate me!{% endblocktrans %}"
        )

        self.assertEqual('Translate me! - translated', template1.render())
        self.gettext.assert_called_with('Translate me!')
        self.assertEqual('alt translated', template2.render())
        self.pgettext.assert_called_with('foo', 'Translate me!')

    def test_trimmed(self):
        template = self.env.from_string("""{% blocktrans trimmed %}
                Translate
                me!
            {% endblocktrans %}""")

        self.assertEqual('Translate me! - translated', template.render())
        self.gettext.assert_called_with('Translate me!')

    def test_with(self):
        template1 = self.env.from_string(
            "{% blocktrans with foo=bar %}Trans: {{ foo }}{% endblocktrans %}"
        )
        template2 = self.env.from_string(
            "{% blocktrans with foo=bar spam=eggs %}Trans: {{ foo }} and "
            "{{ spam }}{% endblocktrans %}"
        )
        template3 = self.env.from_string(
            "{{ foo }} {% blocktrans with foo=bar %}Trans: {{ foo }}"
            "{% endblocktrans %} {{ foo }}"
        )
        template4 = self.env.from_string(
            "{% blocktrans with foo=bar|upper %}Trans: {{ foo }}{% endblocktrans %}"
        )

        self.assertEqual(
            'Trans: barvar - translated',
            template1.render({'bar': 'barvar'})
        )
        self.gettext.assert_called_with('Trans: %(foo)s')
        self.assertEqual(
            'Trans: barvar and eggsvar - translated',
            template2.render({'bar': 'barvar', 'eggs': 'eggsvar'})
        )
        self.gettext.assert_called_with('Trans: %(foo)s and %(spam)s')
        self.assertEqual(
            'foovar Trans: barvar - translated foovar',
            template3.render({'foo': 'foovar', 'bar': 'barvar'})
        )
        self.gettext.assert_called_with('Trans: %(foo)s')
        self.assertEqual(
            'Trans: BARVAR - translated',
            template4.render({'bar': 'barvar'})
        )
        self.gettext.assert_called_with('Trans: %(foo)s')

    def test_global_var(self):
        template = self.env.from_string("{% blocktrans %}Trans: {{ foo }}{% endblocktrans %}")

        self.assertEqual(
            'Trans: foovar - translated',
            template.render({'foo': 'foovar'})
        )
        self.gettext.assert_called_with('Trans: %(foo)s')

    def test_count(self):
        template1 = self.env.from_string(
            "{% blocktrans count counter=foo %}Singular{% plural %}"
            "Plural {{ counter }}{% endblocktrans %}"
        )
        template2 = self.env.from_string(
            """{% blocktrans trimmed count counter=foo %}
                Singular
            {% plural %}
                Plural {{ counter }}
            {% endblocktrans %}"""
        )
        template3 = self.env.from_string(
            "{% blocktrans count counter=foo context 'mycontext' %}"
            "Singular{% plural %}Plural {{ counter }}{% endblocktrans %}"
        )

        self.assertEqual('count translated', template1.render({'foo': 123}))
        self.ngettext.assert_called_with('Singular', 'Plural %(counter)s', 123)
        self.assertEqual('count translated', template2.render({'foo': 123}))
        self.ngettext.assert_called_with('Singular', 'Plural %(counter)s', 123)
        self.assertEqual('count alt translated', template3.render({'foo': 123}))
        self.npgettext.assert_called_with('mycontext', 'Singular', 'Plural %(counter)s', 123)

    def test_count_finalize(self):
        def finalize(value):
            # force convert to string
            return '{}'.format(value)

        self.env.finalize = finalize

        template = self.env.from_string(
            "{% blocktrans count counter=foo %}Singular{% plural %}"
            "Plural {{ counter }}{% endblocktrans %}"
        )
        self.assertEqual('count translated', template.render({'foo': 123}))
        self.ngettext.assert_called_with('Singular', 'Plural %(counter)s', 123)

    def test_count_override_counter(self):
        template = self.env.from_string(
            "{{ my_counter }} "
            "{% blocktrans count my_counter=foo %}Singular {{ my_counter }}"
            "{% plural %}Plural {{ my_counter }}{% endblocktrans %}"
        )
        context = {'my_counter': 123, 'foo': 456}
        self.assertEqual('123 count translated', template.render(context))
        self.ngettext.assert_called_with('Singular %(my_counter)s', 'Plural %(my_counter)s', 456)

    def test_as_var(self):
        template = self.env.from_string(
            "{% blocktrans asvar foo %}Translate me!{% endblocktrans %}"
            "Here comes the translation: {{ foo }}"
        )
        self.assertEqual(
            'Here comes the translation: Translate me! - translated', template.render()
        )
        self.gettext.assert_called_with('Translate me!')

    @override_settings(USE_L10N=True)
    def test_finalize_vars(self):
        def finalize(s):
            if s == 123:
                return 'finalized 123'
            else:
                return s
        self.env.finalize = finalize
        template = self.env.from_string("{% blocktrans %}{{ foo }}{% endblocktrans %}")

        self.assertEqual('finalized 123 - translated', template.render({'foo': 123}))

    def test_errors(self):
        template1 = "{% blocktrans %}foo{% plural %}bar{% endblocktrans %}"
        template2 = "{% blocktrans count counter=10 %}foo{% endblocktrans %}"

        error_messages = [
            (template1, 'used plural without specifying count'),
            (template2, 'plural form not found'),
        ]

        for template, msg in error_messages:
            with self.assertRaisesMessage(TemplateSyntaxError, msg):
                self.env.from_string(template)


@override_settings(USE_L10N=True, USE_TZ=True)
class DjangoL10nTest(SimpleTestCase):
    @requires_tz_support
    def test_localize(self):
        env = Environment(extensions=[DjangoL10n])
        template = env.from_string("{{ foo }}")
        context1 = {'foo': 1.23}
        date = datetime.datetime(2000, 10, 1, 14, 10, 12, tzinfo=timezone.utc)
        context2 = {'foo': date}

        translation.activate('en')
        self.assertEqual('1.23', template.render(context1))

        translation.activate('de')
        self.assertEqual('1,23', template.render(context1))

        translation.activate('es')
        timezone.activate('America/Argentina/Buenos_Aires')
        self.assertEqual('1 de Octubre de 2000 a las 11:10', template.render(context2))

        timezone.activate('Europe/Berlin')
        self.assertEqual('1 de Octubre de 2000 a las 16:10', template.render(context2))

        translation.activate('de')
        self.assertEqual('1. Oktober 2000 16:10', template.render(context2))

        timezone.activate('America/Argentina/Buenos_Aires')
        self.assertEqual('1. Oktober 2000 11:10', template.render(context2))

    def test_existing_finalize(self):
        finalize_mock = mock.Mock(side_effect=lambda s: s)

        class TestExtension(Extension):
            def __init__(self, environment):
                environment.finalize = finalize_mock

        env = Environment(extensions=[TestExtension, DjangoL10n])
        template = env.from_string("{{ foo }}")

        translation.activate('de')
        self.assertEqual('1,23', template.render({'foo': 1.23}))
        finalize_mock.assert_called_with(1.23)


class DjangoStaticTest(SimpleTestCase):
    @staticmethod
    def _static(path):
        return 'Static: {}'.format(path)

    def setUp(self):
        patcher = mock.patch('jdj_tags.extensions.django_static', side_effect=self._static)
        self.static = patcher.start()
        self.addCleanup(patcher.stop)

        self.env = Environment(extensions=[DjangoStatic])

    def test_simple(self):
        template = self.env.from_string("{% static 'static.png' %}")

        self.assertEqual('Static: static.png', template.render())
        self.static.assert_called_with('static.png')

    def test_as_var(self):
        template = self.env.from_string(
            "{% static 'static.png' as my_url %}My url is: {{ my_url }}!"
        )

        self.assertEqual('My url is: Static: static.png!', template.render())
        self.static.assert_called_with('static.png')


class DjangoNowTest(SimpleTestCase):
    @staticmethod
    def _now(tz=None):
        return datetime.datetime(2015, 7, 8, 10, 33, 25, tzinfo=tz)

    def setUp(self):
        patcher = mock.patch('jdj_tags.extensions.datetime')
        dt_mock = patcher.start()
        dt_mock.now.configure_mock(side_effect=self._now)
        self.addCleanup(patcher.stop)

        self.env = Environment(extensions=[DjangoNow])

    def test_simple(self):
        template = self.env.from_string("{% now 'Y-m-d' %}")
        expected = self._now().strftime('%Y-%m-%d')

        self.assertEqual(expected, template.render())

    def test_as_var(self):
        template = self.env.from_string(
            "{% now 'Y-m-d' as cur_date %}Current date is: {{ cur_date }}!"
        )
        expected = "Current date is: %s!" % self._now().strftime('%Y-%m-%d')

        self.assertEqual(expected, template.render())


class DjangoUrlTest(SimpleTestCase):
    @staticmethod
    def _reverse(name, *args, **kwargs):
        return 'Url for: {}'.format(name)

    def setUp(self):
        patcher = mock.patch('jdj_tags.extensions.reverse', side_effect=self._reverse)
        self.reverse = patcher.start()
        self.addCleanup(patcher.stop)

        self.env = Environment(extensions=[DjangoUrl])

    def test_simple(self):
        template = self.env.from_string("{% url 'my_view' %}")

        self.assertEqual('Url for: my_view', template.render())
        self.reverse.assert_called_with('my_view', args=(), kwargs={})

    def test_args(self):
        template1 = self.env.from_string("{% url 'my_view' 'foo' 'bar' %}")
        template2 = self.env.from_string("{% url 'my_view' arg1 'bar' %}")
        template3 = self.env.from_string("{% url 'my_view' arg1 arg2 %}")

        expected = 'Url for: my_view'
        call = mock.call('my_view', args=('foo', 'bar'), kwargs={})

        self.assertEqual(expected, template1.render())
        self.assertEqual(call, self.reverse.call_args)
        self.assertEqual(expected, template2.render({'arg1': 'foo'}))
        self.assertEqual(call, self.reverse.call_args)
        self.assertEqual(expected, template3.render({'arg1': 'foo', 'arg2': 'bar'}))
        self.assertEqual(call, self.reverse.call_args)

    def test_kwargs(self):
        template1 = self.env.from_string("{% url 'my_view' kw1='foo' kw2='bar' %}")
        template2 = self.env.from_string("{% url 'my_view' kw1=arg1 kw2='bar' %}")
        template3 = self.env.from_string("{% url 'my_view' kw1=arg1 kw2=arg2 %}")

        expected = 'Url for: my_view'
        call = mock.call('my_view', args=(), kwargs={'kw1': 'foo', 'kw2': 'bar'})

        self.assertEqual(expected, template1.render())
        self.assertEqual(call, self.reverse.call_args)
        self.assertEqual(expected, template2.render({'arg1': 'foo'}))
        self.assertEqual(call, self.reverse.call_args)
        self.assertEqual(expected, template3.render({'arg1': 'foo', 'arg2': 'bar'}))
        self.assertEqual(call, self.reverse.call_args)

    def test_dotted_expr(self):
        template1 = self.env.from_string("{% url 'my_view' foo.bar %}")
        template2 = self.env.from_string("{% url 'my_view' kw1=foo.bar %}")

        class Foo(object):
            pass

        foo = Foo()
        foo.bar = 'argument'

        self.assertEqual('Url for: my_view', template1.render({'foo': foo}))
        self.reverse.assert_called_with('my_view', args=('argument',), kwargs={})
        self.assertEqual('Url for: my_view', template2.render({'foo': foo}))
        self.reverse.assert_called_with('my_view', args=(), kwargs={'kw1': 'argument'})

    def test_as_var(self):
        template1 = self.env.from_string("{% url 'my_view' as my_url %}Url: {{ my_url }}")
        template2 = self.env.from_string(
            "{% url 'my_view' arg1 'bar' as my_url %}Url: {{ my_url }}"
        )
        template3 = self.env.from_string(
            "{% url 'my_view' kw1=arg1 kw2='bar' as my_url %}Url: {{ my_url }}"
        )

        expected = 'Url: Url for: my_view'

        self.assertEqual(expected, template1.render())
        self.reverse.assert_called_with('my_view', args=(), kwargs={})
        self.assertEqual(expected, template2.render({'arg1': 'foo'}))
        self.reverse.assert_called_with('my_view', args=('foo', 'bar'), kwargs={})
        self.assertEqual(expected, template3.render({'arg1': 'foo'}))
        self.reverse.assert_called_with('my_view', args=(), kwargs={'kw1': 'foo', 'kw2': 'bar'})

    def test_errors(self):
        template = "{% url 'my_view' kw1='foo' 123 %}"
        msg = "got 'integer', expected name for keyword argument"

        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.env.from_string(template)


class DjangoCompatTest(SimpleTestCase):
    classes = ['DjangoCsrf', 'DjangoI18n', 'DjangoStatic', 'DjangoNow', 'DjangoUrl']

    class CalledParse(Exception):
        pass

    @classmethod
    def make_side_effect(cls, cls_name):
        def parse(self, parser):
            raise cls.CalledParse(cls_name)
        return parse

    def setUp(self):
        for class_name in self.classes:
            patcher = mock.patch(
                'jdj_tags.extensions.{}.parse'.format(class_name),
                side_effect=self.make_side_effect(class_name)
            )
            patcher.start()
            self.addCleanup(patcher.stop)

        self.env = Environment(extensions=[DjangoCompat])

    def test_compat(self):
        tags = [
            ('csrf_token', 'DjangoCsrf'),
            ('trans', 'DjangoI18n'),
            ('blocktrans', 'DjangoI18n'),
            ('static', 'DjangoStatic'),
            ('now', 'DjangoNow'),
            ('url', 'DjangoUrl'),
        ]

        for tag, class_name in tags:
            with self.assertRaisesMessage(self.CalledParse, class_name):
                self.env.from_string('{% ' + tag + ' %}')


if __name__ == '__main__':
    import unittest
    from django.apps import apps
    from django.conf import settings
    settings.configure()
    apps.populate(settings.INSTALLED_APPS)

    unittest.main()
