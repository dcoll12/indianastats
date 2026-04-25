# 🚀 GitHub Pages Deployment Guide

Deploy your Indiana District Lookup tool as a **FREE static website on GitHub Pages** - no server required!

## 📦 What You Need

Your download includes:
- ✅ `index.html` - The complete web app (HTML/CSS/JavaScript)
- ✅ `convert_to_json.py` - Converts Excel to JSON
- ✅ `Indiana House Districts by County.xlsx` - Your data

## 🎯 Quick Deploy (5 Minutes)

### Step 1: Convert Excel to JSON

Run this command in your folder:

```bash
python convert_to_json.py
```

This creates `district_data.json` from your Excel file.

### Step 2: Create GitHub Repository

1. Go to https://github.com/new
2. Repository name: `indiana-district-lookup`
3. Make it **Public** (required for free GitHub Pages)
4. ✅ Check "Add a README file"
5. Click "Create repository"

### Step 3: Upload Files

Click **"Add file"** → **"Upload files"**, then drag these 2 files:
- ✅ `index.html`
- ✅ `district_data.json`

Click "Commit changes"

### Step 4: Enable GitHub Pages

1. Go to repository **Settings** (top right)
2. Click **"Pages"** in left sidebar
3. Under "Source", select: **Branch: main** → **/ (root)**
4. Click **Save**
5. Wait 1-2 minutes

### Step 5: Access Your Site! 🎉

Your site is now live at:
```
https://YOUR_USERNAME.github.io/indiana-district-lookup/
```

**That's it!** Your app is now hosted on GitHub Pages for FREE!

---

## 🎨 Customization

### Change the Title

Edit `index.html` and find:

```html
<h1>🏛️ Indiana District Lookup</h1>
```

Change to whatever you want!

### Change Colors

In `index.html`, find the `<style>` section and update:

```css
background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
```

Try different gradients from https://uigradients.com

### Add Your Logo

In `index.html`, add before the `<h1>`:

```html
<img src="logo.png" alt="Logo" style="width: 100px;">
```

Then upload `logo.png` to GitHub.

---

## 🔄 Updating Your Data

When your Excel file changes:

1. Run: `python convert_to_json.py` (creates new JSON)
2. Upload the new `district_data.json` to GitHub
3. Changes appear instantly (may need to refresh browser)

---

## 🌐 Custom Domain

Want `districts.yoursite.com` instead of GitHub's URL?

### Step 1: Buy a Domain
- Namecheap, Google Domains, etc. (~$12/year)

### Step 2: Configure DNS

Add these DNS records at your domain registrar:

```
Type: A
Host: @
Value: 185.199.108.153

Type: A  
Host: @
Value: 185.199.109.153

Type: A
Host: @
Value: 185.199.110.153

Type: A
Host: @
Value: 185.199.111.153

Type: CNAME
Host: www
Value: YOUR_USERNAME.github.io
```

### Step 3: Configure GitHub

1. In repo Settings → Pages
2. Enter your domain in "Custom domain"
3. Click Save
4. ✅ Check "Enforce HTTPS"

Wait 10-20 minutes for DNS to propagate!

---

## 📱 How It Works

This is a **static web application**:

- ✅ No server needed - runs entirely in browser
- ✅ Fast - everything loads locally
- ✅ Free - GitHub Pages is 100% free
- ✅ Reliable - hosted by GitHub's infrastructure
- ✅ HTTPS - secure by default

**Data flow:**
```
Excel file → convert_to_json.py → district_data.json → index.html loads it → User searches
```

---

## 🛠️ Advanced Features

### Add Google Analytics

1. Get tracking ID from https://analytics.google.com
2. Add before `</head>` in `index.html`:

```html
<script async src="https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'G-XXXXXXXXXX');
</script>
```

### Make it a PWA (Progressive Web App)

Create `manifest.json`:

```json
{
  "name": "Indiana District Lookup",
  "short_name": "IN Districts",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#667eea",
  "theme_color": "#667eea",
  "icons": [
    {
      "src": "icon-192.png",
      "sizes": "192x192",
      "type": "image/png"
    }
  ]
}
```

Add to `<head>` in `index.html`:

```html
<link rel="manifest" href="manifest.json">
```

Now it can be "installed" on phones!

---

## 📂 Repository Structure

```
your-repo/
├── index.html              ← Main app
├── district_data.json      ← District data
├── README.md              ← Documentation
└── convert_to_json.py     ← Converter (optional in repo)
```

You only **need** to upload `index.html` and `district_data.json` to GitHub.

---

## 🐛 Troubleshooting

### "404 Not Found"
- Wait 2-3 minutes after enabling Pages
- Check Settings → Pages shows the URL
- Make sure repository is **Public**

### "Data not loading"
- Check `district_data.json` is uploaded
- Open browser console (F12) for errors
- Verify JSON is valid at: https://jsonlint.com

### "Page looks broken"
- Hard refresh: Ctrl+Shift+R (Windows) or Cmd+Shift+R (Mac)
- Clear browser cache
- Check browser console for errors

### Changes don't appear
- GitHub Pages can take 1-2 minutes to update
- Clear your browser cache
- Try incognito/private mode

---

## ✅ Deployment Checklist

- [ ] Converted Excel to JSON (`python convert_to_json.py`)
- [ ] Created GitHub repository (public)
- [ ] Uploaded `index.html`
- [ ] Uploaded `district_data.json`
- [ ] Enabled GitHub Pages in Settings
- [ ] Waited 2 minutes for deployment
- [ ] Tested site URL
- [ ] County lookup works
- [ ] District lookup works
- [ ] Mobile view works

---

## 🔒 Security & Privacy

### Making Repository Private

GitHub Pages on **free** accounts requires **public** repos. Options:

1. **GitHub Pro** ($4/month) - allows private repos with Pages
2. **Keep public** - but `district_data.json` is visible to everyone
3. **Obfuscate data** - minify JSON (makes it harder to read)

### Minify JSON

```bash
# Install jq (JSON processor)
# Mac: brew install jq
# Windows: download from https://stedolan.github.io/jq/

# Minify
jq -c . district_data.json > district_data.min.json
```

Then update `index.html` to load `district_data.min.json` instead.

---

## 📊 Monitoring

### Check Site Status

Visit: https://YOUR_USERNAME.github.io/indiana-district-lookup/

### View Traffic

GitHub doesn't provide analytics. Use:
- Google Analytics (free)
- Cloudflare Analytics (free)
- Simple Analytics ($19/mo)

### Monitor Uptime

GitHub Pages has 99.9%+ uptime, but you can monitor with:
- UptimeRobot (free) - https://uptimerobot.com
- StatusCake (free tier) - https://www.statuscake.com

---

## 🚀 Performance Tips

### 1. Minify HTML

Use: https://www.minifier.org
Paste `index.html`, get minified version, upload

### 2. Compress JSON

Already pretty compact, but you can use `jq -c`

### 3. Enable Caching

Add to `<head>`:

```html
<meta http-equiv="Cache-Control" content="max-age=31536000">
```

### 4. Use CDN

GitHub Pages is already on a CDN (Fastly), so you're good!

---

## 🎓 Learning Resources

- [GitHub Pages Docs](https://docs.github.com/en/pages)
- [Markdown Guide](https://www.markdownguide.org/)
- [HTML/CSS/JS Tutorial](https://www.w3schools.com/)

---

## 💡 Pro Tips

1. **Star your repo** so you can find it easily
2. **Add topics** (Settings → scroll down) like `indiana`, `districts`, `lookup`
3. **Write a good README** to explain what it does
4. **Add a license** (Settings → Add file → Create LICENSE → choose MIT)
5. **Enable issues** for bug reports and feature requests

---

## 🎉 You're Done!

Your Indiana District Lookup tool is now:
- ✅ Hosted on GitHub Pages
- ✅ Accessible via clean URL
- ✅ Free forever
- ✅ Fast and reliable
- ✅ Easy to update

**Share your URL with the world!**

Example: https://yourusername.github.io/indiana-district-lookup/

---

## 📧 Need Help?

- GitHub Pages Issues: https://github.com/community
- HTML/CSS/JS Help: https://stackoverflow.com
- This project: Open an issue on your GitHub repo

---

**Congratulations on deploying your first static web app! 🎊**
