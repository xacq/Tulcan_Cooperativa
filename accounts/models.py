from django.db import models
from django.contrib.auth.models import User

class LoginAudit(models.Model):
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.CharField(max_length=64, blank=True, default="")
    user_agent = models.TextField(blank=True, default="")
    success = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.timestamp} | {self.user} | success={self.success}"


# Create your models here.
