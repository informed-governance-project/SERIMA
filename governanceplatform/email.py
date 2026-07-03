# governanceplatform/mail.py
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils.encoding import force_bytes, force_str


class Base64EmailMultiAlternatives(EmailMultiAlternatives):
    """
    Django 6.0's EmailMessage.message() lets Python's modern email API
    (email.policy.default) pick the Content-Transfer-Encoding automatically.
    For text/plain UTF-8 bodies with long lines (e.g. password reset URLs),
    it silently falls back to quoted-printable, which inserts soft line
    breaks ('=\\r\\n') that some webmail clients (notably Gmail) fail to
    reassemble before auto-linkifying the URL, corrupting the link.

    Forcing cte="base64" avoids any line-length-triggered soft-wrapping,
    since base64 has no notion of "meaningful" line content.
    """

    def _add_bodies(self, msg):
        if self.body or not self.alternatives:
            encoding = self.encoding or settings.DEFAULT_CHARSET
            body = force_str(self.body or "", encoding=encoding, errors="surrogateescape")
            msg.set_content(body, subtype=self.content_subtype, charset=encoding, cte="base64")
        if self.alternatives:
            msg.make_alternative()
            encoding = self.encoding or settings.DEFAULT_CHARSET
            for alternative in self.alternatives:
                maintype, subtype = alternative.mimetype.split("/", 1)
                content = alternative.content
                if maintype == "text":
                    if isinstance(content, bytes):
                        content = content.decode()
                    msg.add_alternative(content, subtype=subtype, charset=encoding, cte="base64")
                else:
                    content = force_bytes(content, encoding=encoding, strings_only=True)
                    msg.add_alternative(content, maintype=maintype, subtype=subtype)
        return msg
