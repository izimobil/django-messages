import re
import django
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
try:
    from django.utils.importlib import import_module
except ImportError:
    from importlib import import_module
from django.utils.text import wrap
from django.utils.translation import ugettext, ugettext_lazy as _
from django.template.loader import render_to_string
from django.conf import settings
from django.core.paginator import Paginator, InvalidPage

# favour django-mailer but fall back to django.core.mail

if "mailer" in settings.INSTALLED_APPS:
    from mailer import send_mail
else:
    from django.core.mail import send_mail


PAGE_LENGTH = getattr(settings, 'DJANGO_MESSAGES_PAGE_LENGTH', -1)


def format_quote(sender, body):
    """
    Wraps text at 55 chars and prepends each
    line with `> `.
    Used for quoting messages in replies.
    """
    lines = wrap(body, 55).split('\n')
    for i, line in enumerate(lines):
        lines[i] = "> %s" % line
    quote = '\n'.join(lines)
    return ugettext(u"%(sender)s wrote:\n%(body)s") % {
        'sender': sender,
        'body': quote
    }

def format_subject(subject):
    """
    Prepends 'Re:' to the subject. To avoid multiple 'Re:'s
    a counter is added.
    NOTE: Currently unused. First step to fix Issue #48.
    FIXME: Any hints how to make this i18n aware are very welcome.

    """
    subject_prefix_re = r'^Re\[(\d*)\]:\ '
    m = re.match(subject_prefix_re, subject, re.U)
    prefix = u""
    if subject.startswith('Re: '):
        prefix = u"[2]"
        subject = subject[4:]
    elif m is not None:
        try:
            num = int(m.group(1))
            prefix = u"[%d]" % (num+1)
            subject = subject[6+len(str(num)):]
        except:
            # if anything fails here, fall back to the old mechanism
            pass

    return ugettext(u"Re%(prefix)s: %(subject)s") % {
        'subject': subject,
        'prefix': prefix
    }

def new_message_email(sender, instance, signal,
        subject_prefix=_(u'New Message: %(subject)s'),
        template_name="django_messages/new_message.html",
        default_protocol=None,
        *args, **kwargs):
    """
    This function sends an email and is called via Django's signal framework.
    Optional arguments:
        ``template_name``: the template to use
        ``subject_prefix``: prefix for the email subject.
        ``default_protocol``: default protocol in site URL passed to template
    """
    if default_protocol is None:
        default_protocol = getattr(settings, 'DEFAULT_HTTP_PROTOCOL', 'http')

    if 'created' in kwargs and kwargs['created']:
        try:
            from django.contrib.sites.models import Site
            current_domain = Site.objects.get_current().domain
            subject = subject_prefix % {'subject': instance.subject}
            message = render_to_string(template_name, {
                'site_url': '%s://%s' % (default_protocol, current_domain),
                'message': instance,
            })
            if instance.recipient.email != "":
                send_mail(subject, message, settings.DEFAULT_FROM_EMAIL,
                    [instance.recipient.email,])
        except Exception as e:
            #print e
            pass #fail silently


def get_user_model():
    if django.VERSION[:2] >= (1, 5):
        from django.contrib.auth import get_user_model
        return get_user_model()
    else:
        from django.contrib.auth.models import User
        return User


def get_username_field():
    if django.VERSION[:2] >= (1, 5):
        return get_user_model().USERNAME_FIELD
    else:
        return 'username'


def get_storage_backend():
    """
    Return an instance of ``django.core.files.storage.Storage``.

    The instance is built from ``DJANGO_MESSAGES_STORAGE_BACKEND``
    string variable and ``DJANGO_MESSAGES_STORAGE_BACKEND_KWARGS``
    dictionary variable.
    """
    path = getattr(settings, 'DJANGO_MESSAGES_STORAGE_BACKEND', None)

    if path is None:
        return None
    try:
        mod_name, klass_name = path.rsplit('.', 1)
        mod = import_module(mod_name)
    except AttributeError as e:
        raise ImproperlyConfigured(
            'Error importing storage backend %s: "%s"' % (mod_name, e)
        )
    try:
        klass = getattr(mod, klass_name)
    except AttributeError:
        raise ImproperlyConfigured(
            'Module "%s" does not define a "%s" class' %
            (mod_name, klass_name)
        )
    kwargs = getattr(settings, 'DJANGO_MESSAGES_STORAGE_BACKEND_KWARGS', {})
    return klass(**kwargs)


def paginate_queryset(request, qs):
    if PAGE_LENGTH == -1:
        # Disable pagination
        return qs
    paginator = Paginator(qs, PAGE_LENGTH)
    page_num = request.GET.get('page', 1)
    try:
        return paginator.page(page_num)
    except InvalidPage:
        return paginator.page(1)
