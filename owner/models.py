from django.db import models

class AppReport(models.Model):
    report_date = models.DateField(auto_now_add=True)
    new_users = models.IntegerField()
    active_patients = models.IntegerField()
    total_revenue = models.FloatField()
    feedback_summary = models.TextField(blank=True)

    def __str__(self):
        return f"Report on {self.report_date}"

