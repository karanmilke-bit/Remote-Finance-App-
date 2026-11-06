# PulseFinance ₹ • Cloud & Mobile Personal Finance App

A cloud-synchronized personal finance tracking application with **Indian Rupee (₹)** formatting, **Supabase PostgreSQL** cloud persistence, and a mobile-optimized web app ready to deploy on **Vercel** with one click.

---

## 🚀 Live Cloud Architecture

- **Database:** Supabase PostgreSQL (`public.finance_transactions`)
- **Hosting & CDN:** Vercel (Static Web App & PWA)
- **Frontend:** Modern Tailwind CSS + Lucide Icons + Chart.js + Supabase JS Client
- **Mobile Support:** PWA (Progressive Web App) with "Add to Home Screen" for iPhone & Android
- **Desktop Companion:** Python CustomTkinter bridge (`app_supabase.py`)

---

## 🛠️ Supabase Database Configuration (Completed)

Your Supabase project is already configured with:
- **Project URL:** `https://lggevcvmtxpngeilsnba.supabase.co`
- **Table:** `public.finance_transactions`
  - `id`: UUID (Primary Key)
  - `title`: TEXT (Description)
  - `category`: TEXT (Rent, Groceries, Dining, Freelance, Salary, etc.)
  - `amount`: NUMERIC (Positive amount in ₹)
  - `transaction_date`: DATE (YYYY-MM-DD)
  - `is_income`: BOOLEAN (`true` for Income, `false` for Expense)
  - `note`: TEXT (Optional notes, tags)
  - `created_at`: TIMESTAMPTZ
- **Row Level Security (RLS):** Fully configured with `SELECT`, `INSERT`, `UPDATE`, and `DELETE` policies for public/authenticated access.

---

## 📦 How to Push to GitHub & Deploy to Vercel

### Step 1: Initialize Git and Push to GitHub

In your project folder, run:

```bash
git init
git add .
git commit -m "feat: PulseFinance Vercel and Supabase cloud integration"
```

Create a new repository on your GitHub account (e.g. `pulse-finance`), then link and push:

```bash
git branch -M main
git remote add origin https://github.com/<your-username>/pulse-finance.git
git push -u origin main
```

---

### Step 2: Deploy to Vercel

1. Log in to your [Vercel Dashboard](https://vercel.com).
2. Click **"Add New"** > **"Project"**.
3. Select your newly pushed GitHub repository (`pulse-finance`).
4. **Framework Preset:** Choose **"Other"** (or leave as Default).
5. **Environment Variables (Optional):**
   Vercel allows setting environment variables under the **Environment Variables** accordion:
   - `NEXT_PUBLIC_SUPABASE_URL`: `https://lggevcvmtxpngeilsnba.supabase.co`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY`: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxnZ2V2Y3ZtdHhwbmdlaWxzbmJhIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODQ4NzA2MzAsImV4cCI6MjEwMDQ0NjYzMH0.r-_pzew2NV_msvj92Y6b29GFaQkZ9LmoJ9S9sAdHvcI`
   *(The app also has your project pre-configured out-of-the-box in `index.html`).*
6. Click **"Deploy"**. Within ~15 seconds, Vercel will give you a live production URL (e.g., `https://pulse-finance-xyz.vercel.app`).

---

## 📱 How to Use on Your Phone (Android / iPhone)

1. Open your live Vercel URL in **Safari** (iPhone) or **Chrome** (Android).
2. **Install as a Native App:**
   - **iPhone (Safari):** Tap the **Share** button (box with upward arrow) > scroll down and tap **"Add to Home Screen"**.
   - **Android (Chrome):** Tap the **Three Dots (⋮)** in the top right > tap **"Add to Home Screen"** (or "Install App").
3. Launch PulseFinance from your home screen icon — it opens in fullscreen standalone mode without browser bars, exactly like a native app.
4. Add, edit, or delete transactions anytime; they sync in real-time with your Supabase cloud database!
