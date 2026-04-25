# 🚀 How to Deploy YOUR App to GitHub Pages

## 📋 What You Have

- ✅ `index.html` - Your web app
- ✅ `convert_to_json.py` - Converter script
- ✅ `Indiana House Districts by County.xlsx` - Your Excel file

## 🎯 Step-by-Step Instructions

### Step 1: Convert Your Excel File to JSON

Open your terminal/command prompt in the folder with your files and run:

**Windows:**
```cmd
python convert_to_json.py "Indiana House Districts by County.xlsx"
```

**Mac/Linux:**
```bash
python3 convert_to_json.py "Indiana House Districts by County.xlsx"
```

**✅ Success!** You should now have a file called `district_data.json`

---

### Step 2: Test Locally (Optional but Recommended)

1. Open the folder with your files
2. Double-click `index.html`
3. It should open in your browser and work!

If you see "Error loading district data", make sure:
- `district_data.json` is in the SAME folder as `index.html`
- You completed Step 1 successfully

---

### Step 3: Create GitHub Repository

1. Go to **https://github.com/new**
2. Fill in:
   - **Repository name:** `indiana-district-lookup` (or any name you want)
   - **Description:** "Indiana legislative district lookup tool"
   - **Public** (must be public for free GitHub Pages)
   - ✅ Check **"Add a README file"**
3. Click **"Create repository"**

---

### Step 4: Upload Your Files

You need to upload **2 files** to GitHub:

**Method A - Web Interface (Easiest):**

1. In your new repository, click **"Add file"** → **"Upload files"**
2. Drag these 2 files into the upload area:
   - ✅ `index.html`
   - ✅ `district_data.json`
3. Scroll down and click **"Commit changes"**

**Method B - Command Line:**

```bash
cd your-folder
git init
git add index.html district_data.json
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/indiana-district-lookup.git
git push -u origin main
```

---

### Step 5: Enable GitHub Pages

1. In your repository, click **"Settings"** (top menu bar)
2. Click **"Pages"** in the left sidebar
3. Under **"Source"**, select:
   - Branch: **main**
   - Folder: **/ (root)**
4. Click **"Save"**
5. Wait 1-2 minutes

---

### Step 6: Get Your URL

At the top of the Pages settings, you'll see:

```
Your site is published at:
https://YOUR_USERNAME.github.io/indiana-district-lookup/
```

**Click that link!** Your app is now live! 🎉

---

## ✅ Verification Checklist

Test your live site:

- [ ] Site loads (no 404 error)
- [ ] Statistics show at the top (92 counties, etc.)
- [ ] County autocomplete works when you type
- [ ] Typing "Marion" shows districts
- [ ] Entering district numbers shows counties
- [ ] Works on your phone

---

## 🐛 Troubleshooting

### "Error loading district data"

**Problem:** The `district_data.json` file is missing or in the wrong place.

**Solution:**
1. Make sure you ran `python convert_to_json.py` successfully
2. Verify `district_data.json` exists in your folder
3. Re-upload to GitHub if needed

---

### "404 - File not found"

**Problem:** GitHub Pages isn't enabled or files aren't uploaded.

**Solution:**
1. Check Settings → Pages shows a green checkmark
2. Make sure both `index.html` and `district_data.json` are uploaded
3. Wait 2-3 minutes after uploading

---

### "Convert script doesn't work"

**Problem:** Python isn't installed or wrong command.

**Solutions:**

**If Python isn't installed:**
- Download from https://python.org/downloads/
- Install and try again

**If you get "command not found":**
- Try `python3` instead of `python`
- Or `py` on Windows

**If you get "pandas not found":**
```bash
pip install pandas openpyxl
```

Then run the convert command again.

---

### "Can't find the Excel file"

**Problem:** File path is wrong.

**Solution:**
Make sure you're in the same folder as the Excel file:

```bash
# See your current folder
pwd  # Mac/Linux
cd   # Windows

# List files
ls  # Mac/Linux  
dir # Windows

# You should see "Indiana House Districts by County.xlsx"
```

If not, navigate to the correct folder:
```bash
cd path/to/your/folder
```

---

## 🔄 Updating Your Data

When your Excel file changes:

1. **Run converter again:**
   ```bash
   python convert_to_json.py "Indiana House Districts by County.xlsx"
   ```

2. **Upload new JSON to GitHub:**
   - Go to your repository
   - Click on `district_data.json`
   - Click the pencil icon (✏️) to edit
   - Delete all content
   - Copy/paste content from your new file
   - Click "Commit changes"

3. **Done!** Refresh your website (may need hard refresh: Ctrl+Shift+R)

---

## 📱 Share Your Site

Your URL is:
```
https://YOUR_USERNAME.github.io/indiana-district-lookup/
```

Share it with:
- ✉️ Email
- 📱 Text message
- 🐦 Social media
- 📄 Add to documentation

---

## 💡 Quick Tips

**Bookmark your repository:**
```
https://github.com/YOUR_USERNAME/indiana-district-lookup
```

**Keep the Excel file:**
You'll need it when data updates.

**Don't upload the Excel file to GitHub:**
It's not needed for the website and keeps your repo small.

**Test locally first:**
Always double-click `index.html` to test before uploading.

---

## 🎉 That's It!

You now have a live website on GitHub Pages!

**Free forever**
**Fast and reliable**
**Easy to update**

---

## ❓ Still Stuck?

If you're having trouble with a specific step, let me know which step number and what error you're seeing!
