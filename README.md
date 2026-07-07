# MyValidCV README

## Project Setup

### 1. Create Virtual Environment
```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run Migrations
```bash
python manage.py migrate
```

### 4. Create Superuser (Optional)
```bash
python manage.py createsuperuser
```

### 5. Run Development Server
```bash
python manage.py runserver
```

Visit: http://localhost:8000

## Features

### MVP User Journey
1. Guest opens landing page
2. Guest uploads CV file (PDF, DOCX, TXT)
3. Guest pastes job description
4. System validates inputs and extracts data
5. System generates ATS-style match report
6. Guest sees preview result
7. Guest can register/login to save results

### ATS Analysis Includes
- Overall match score
- ATS compatibility score
- Skills matching
- Keywords matching
- Experience analysis
- Qualification matching
- Format assessment
- Recommendations

### Usage Limits
- Free: 2 analyses per day
- Professional: 5 analyses per day
- Enterprise: 200 analyses per month

## File Structure

```
MyValidCV_clean/
├── config/              # Main Django config
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── core/                # Main app (landing, analysis)
│   ├── services.py      # ATS extraction engine
│   ├── views.py         # Home, analyse, results
│   ├── models.py        # Analysis model
│   └── urls.py
├── accounts/            # Authentication
│   ├── views.py         # Register, login
│   ├── forms.py         # Auth forms
│   ├── models.py        # UserProfile
│   └── signals.py       # Auto profile creation
├── dashboard/           # User dashboard
│   ├── views.py
│   └── urls.py
├── templates/           # HTML templates
│   ├── base.html
│   ├── landing/
│   │   ├── home.html
│   │   └── results_preview.html
│   ├── accounts/
│   │   ├── login.html
│   │   └── register.html
│   └── dashboard/
│       └── home.html
├── static/
│   ├── css/
│   │   └── style.css    # Custom SaaS styling
│   └── js/
│       └── main.js      # Theme & form handling
├── manage.py
└── requirements.txt
```

## API Endpoints

### Public Routes
- `GET  /`                  - Landing page
- `POST /analyse/`          - Submit CV and JD
- `GET  /results/`          - View results
- `GET  /register/`         - Sign up page
- `POST /register/`         - Create account
- `GET  /login/`            - Login page
- `POST /login/`            - Authenticate
- `POST /logout/`           - Logout

### Protected Routes
- `GET  /dashboard/`        - User dashboard

### Admin
- `GET  /admin/`            - Django admin

## Testing the MVP

### Test Case 1: Valid CV + Valid JD
1. Go to homepage
2. Upload sample CV (PDF/DOCX/TXT)
3. Paste a job description
4. Click "Validate My CV"
5. Should see results preview with all scores

### Test Case 2: Invalid Inputs
1. Try uploading empty file
2. Try without job description
3. Verify error messages

### Test Case 3: File Types
1. Test with PDF, DOCX, TXT files
2. Verify all parse correctly

### Test Case 4: Authentication
1. Sign up with new account
2. Login/logout
3. Access protected dashboard
4. Verify analysis history

## Technologies Used

- **Backend**: Django 6 (Python)
- **Database**: SQLite (development)
- **Frontend**: Bootstrap 5.3, Vanilla JS
- **PDF Parsing**: pypdf
- **DOCX Parsing**: python-docx
- **ATS Engine**: Custom extraction logic

## Important Notes

- **Privacy**: CV and job description files are NOT permanently stored
- **Sessions**: Results stored temporarily in Django sessions
- **No File Storage**: Analysis is done in-memory
- **Future**: Database models ready for when we save history

## Customization

### Add Custom CSS
Edit `static/css/style.css` - uses CSS variables for colors

### Change Colors
Modify CSS variables in `style.css`:
```css
--primary: #667eea;
--success: #48bb78;
--warning: #f6ad55;
```

### Update ATS Logic
Edit `core/services.py` - modify skill keywords and matching algorithm

## Troubleshooting

### ModuleNotFoundError
```bash
pip install -r requirements.txt
```

### Database errors
```bash
python manage.py migrate
```

### Port already in use
```bash
python manage.py runserver 8001
```

## Future Enhancements

1. Save analysis history
2. Compare multiple job analyses
3. AI-powered recommendations
4. Export reports to PDF
5. API for programmatic access
6. Stripe payment integration
7. Email notifications
8. Admin dashboard

## Support

For issues or questions, please check the code comments in:
- `core/services.py` - ATS algorithm
- `core/views.py` - Request handling
- `static/js/main.js` - Frontend logic
