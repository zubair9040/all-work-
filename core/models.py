from django.db import models


class TimeStamped(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class NumberedMixin(models.Model):
    """Assigns a human-readable document number (e.g. SO-000042) after first save."""

    number_prefix = "DOC"
    number = models.CharField(max_length=20, unique=True, blank=True, editable=False)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.number:
            self.number = f"{self.number_prefix}-{self.pk:06d}"
            type(self).objects.filter(pk=self.pk).update(number=self.number)

    def __str__(self):
        return self.number


class ERPError(Exception):
    """Business-rule violation (e.g. insufficient stock)."""
