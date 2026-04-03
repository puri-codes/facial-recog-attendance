from django import forms
from .models import Faculty, AcademicClass, Student


COUNTRY_CODE_CHOICES = [
    ('+977', 'Nepal (+977)'),
    ('+91', 'India (+91)'),
    ('+1', 'USA/Canada (+1)'),
    ('+44', 'UK (+44)'),
    ('+61', 'Australia (+61)'),
]


def _split_phone_value(value, default_code='+977'):
    value = (value or '').strip()
    if not value:
        return default_code, ''

    for code, _ in COUNTRY_CODE_CHOICES:
        if value.startswith(code):
            return code, value[len(code):].strip()

    return default_code, value


def _merge_phone_value(code, number):
    code = (code or '').strip()
    number = (number or '').strip()
    if not number:
        return ''
    if number.startswith('+'):
        return number
    return f'{code}{number}'


class FacultyForm(forms.ModelForm):
    class Meta:
        model = Faculty
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Faculty name'}),
            'description': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3, 'placeholder': 'Description (optional)'}),
        }


class AcademicClassForm(forms.ModelForm):
    class Meta:
        model = AcademicClass
        fields = ['name', 'faculty', 'teacher']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Class name'}),
            'faculty': forms.Select(attrs={'class': 'form-select'}),
            'teacher': forms.Select(attrs={'class': 'form-select'}),
        }


class StudentForm(forms.ModelForm):
    phone_country_code = forms.ChoiceField(
        choices=COUNTRY_CODE_CHOICES,
        initial='+977',
        required=False,
        widget=forms.Select(attrs={'class': 'form-select', 'style': 'max-width: 180px;'}),
        label='Student Phone Country Code',
    )
    guardian_phone_country_code = forms.ChoiceField(
        choices=COUNTRY_CODE_CHOICES,
        initial='+977',
        required=False,
        widget=forms.Select(attrs={'class': 'form-select', 'style': 'max-width: 180px;'}),
        label='Guardian Phone Country Code',
    )

    class Meta:
        model = Student
        fields = [
            'full_name', 'profile_image', 'enrollment_year',
            'faculty', 'academic_class', 'phone', 'guardian_phone',
        ]
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Full name'}),
            'profile_image': forms.ClearableFileInput(attrs={'class': 'form-file', 'accept': 'image/*'}),
            'enrollment_year': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': 'e.g. 2025'}),
            'faculty': forms.Select(attrs={'class': 'form-select'}),
            'academic_class': forms.Select(attrs={'class': 'form-select'}),
            'phone': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Phone number'}),
            'guardian_phone': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Guardian phone'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        phone_value = self.initial.get('phone') if 'phone' in self.initial else getattr(self.instance, 'phone', '')
        guardian_phone_value = (
            self.initial.get('guardian_phone') if 'guardian_phone' in self.initial
            else getattr(self.instance, 'guardian_phone', '')
        )

        phone_code, phone_number = _split_phone_value(phone_value)
        guardian_code, guardian_number = _split_phone_value(guardian_phone_value)

        self.fields['phone_country_code'].initial = phone_code
        self.fields['guardian_phone_country_code'].initial = guardian_code
        self.fields['phone'].initial = phone_number
        self.fields['guardian_phone'].initial = guardian_number

        self.order_fields([
            'full_name', 'profile_image', 'enrollment_year',
            'faculty', 'academic_class',
            'phone_country_code', 'phone',
            'guardian_phone_country_code', 'guardian_phone',
        ])

    def clean(self):
        cleaned_data = super().clean()
        cleaned_data['phone'] = _merge_phone_value(
            cleaned_data.get('phone_country_code'),
            cleaned_data.get('phone'),
        )
        cleaned_data['guardian_phone'] = _merge_phone_value(
            cleaned_data.get('guardian_phone_country_code'),
            cleaned_data.get('guardian_phone'),
        )
        return cleaned_data


class StudentWebcamForm(forms.Form):
    """Form for capturing student photo via webcam."""
    full_name = forms.CharField(
        max_length=300,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Full name'})
    )
    enrollment_year = forms.IntegerField(
        widget=forms.NumberInput(attrs={'class': 'form-input', 'placeholder': 'e.g. 2025'})
    )
    faculty = forms.ModelChoiceField(
        queryset=Faculty.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    academic_class = forms.ModelChoiceField(
        queryset=AcademicClass.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    phone = forms.CharField(
        max_length=20, required=False,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Phone number'})
    )
    phone_country_code = forms.ChoiceField(
        choices=COUNTRY_CODE_CHOICES,
        initial='+977',
        required=False,
        widget=forms.Select(attrs={'class': 'form-select', 'style': 'max-width: 180px;'}),
        label='Student Phone Country Code',
    )
    guardian_phone = forms.CharField(
        max_length=20, required=False,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Guardian phone'})
    )
    guardian_phone_country_code = forms.ChoiceField(
        choices=COUNTRY_CODE_CHOICES,
        initial='+977',
        required=False,
        widget=forms.Select(attrs={'class': 'form-select', 'style': 'max-width: 180px;'}),
        label='Guardian Phone Country Code',
    )
    webcam_image = forms.CharField(
        widget=forms.HiddenInput(),
        help_text='Base64-encoded webcam capture'
    )

    field_order = [
        'full_name',
        'enrollment_year',
        'faculty',
        'academic_class',
        'phone_country_code',
        'phone',
        'guardian_phone_country_code',
        'guardian_phone',
        'webcam_image',
    ]

    def clean(self):
        cleaned_data = super().clean()
        cleaned_data['phone'] = _merge_phone_value(
            cleaned_data.get('phone_country_code'),
            cleaned_data.get('phone'),
        )
        cleaned_data['guardian_phone'] = _merge_phone_value(
            cleaned_data.get('guardian_phone_country_code'),
            cleaned_data.get('guardian_phone'),
        )
        return cleaned_data
