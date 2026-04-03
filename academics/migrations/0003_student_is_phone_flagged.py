from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('academics', '0002_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='student',
            name='is_phone_flagged',
            field=models.BooleanField(
                default=False,
                help_text='Mark this when the student phone number is incorrect.',
            ),
        ),
    ]
