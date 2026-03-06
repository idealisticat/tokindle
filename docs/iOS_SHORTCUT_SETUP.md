# iOS Shortcut Setup for TOKINDLE (Detailed, Step-by-Step)

This guide walks you through creating an iOS Shortcut that sends a WeChat article URL to your TOKINDLE backend. The backend will fetch the article, generate an EPUB, save it to `output/` on the machine running the server, and return the file path.

---

## Prerequisites

1. **Backend running on your Mac** (or another machine on your network), with the server reachable from your iPhone.
2. **Same Wi‑Fi** (recommended): iPhone and the Mac running TOKINDLE are on the same local network.  
   Alternatively, you can use **tunneling** (e.g. ngrok) for access from other networks; see the end of this document.

---

## Part A: Start the backend so the iPhone can reach it

### A.1 Start the server on your Mac

Open **Terminal** and run one of the following from the TOKINDLE project folder:

```bash
cd /path/to/tokindle
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Or use the helper script (if available):

```bash
./run_lan.sh
```

The `--host 0.0.0.0` option makes the server listen on all network interfaces so your phone can connect via your Mac’s local IP address.

### A.2 Find your Mac’s local IP address

Use either method:

- **System Settings** → **Network** → **Wi‑Fi** → **Details** (or **Advanced**) → note the **IP address** (e.g. `192.168.1.10`).
- Or in Terminal: run `ipconfig getifaddr en0` and note the output (e.g. `192.168.1.10`).

### A.3 Test from your iPhone

On your iPhone, open **Safari** and go to:

`http://YOUR_MAC_IP:8000/ping`

Replace `YOUR_MAC_IP` with the IP from A.2 (e.g. `http://192.168.1.10:8000/ping`).

You should see: `{"ping":"pong"}`. If you do, the Shortcut will be able to reach the backend. If not, check that iPhone and Mac are on the same Wi‑Fi and that no firewall is blocking port 8000.

---

## Part B: Create the Shortcut

### B.1 Open the Shortcuts app and create a new shortcut

1. On your iPhone, open the **Shortcuts** app (preinstalled by Apple).
2. Tap the **+** button (top right) to create a new shortcut.
3. Tap **Add Action** (or the search/plus area in the canvas) to start adding steps.

### B.2 Get the article URL (choose one of two flows)

**Option 1 — From clipboard (e.g. after copying the link in WeChat)**

1. In the action search box, type **Clipboard** and add the action **Get Clipboard**.
2. Add another action: search for **Set Variable** and add it.
3. For the variable name, type e.g. `ArticleURL`.
4. For the value, tap and select **Clipboard** (the output of the previous action).

**Option 2 — Ask for input each time**

1. Search for **Ask for Input** and add it.
2. Set the prompt to something like: `Paste the WeChat article link`.
3. Set the input type to **Text**.
4. Add **Set Variable**; name it e.g. `ArticleURL`, and set the value to **Provided Input** (the output of “Ask for Input”).

### B.3 Call the TOKINDLE API

1. Add an action: search for **Get Contents of URL** (or **URL** → **Get Contents of URL**) and add it.
2. **URL**  
   Tap the URL field and enter (replace with your Mac’s IP and port if different):
   ```
   http://YOUR_MAC_IP:8000/parse-url
   ```
   Example: `http://192.168.1.10:8000/parse-url`  
   Do **not** omit `/parse-url`.

3. Expand **Show More** (or the disclosure arrow) for this action so you see **Method**, **Headers**, and **Request Body**.

4. **Method**  
   Set to **POST**.

5. **Headers**  
   Add one header:
   - **Key**: `Content-Type`
   - **Value**: `application/json`

6. **Request Body**  
   Set to **JSON** (or **JSON (Request Body)**).  
   You need to send a JSON object with one key, `url`, whose value is the article URL.

   **How to set the JSON body in Shortcuts:**
   - If the action offers a **JSON** dictionary editor: add a key `url` and for its value tap and choose the variable **ArticleURL** (or whatever you named it in B.2).
   - If you use **Text** to build the body: create a text block like `{"url":" "}` and use **Select Variable** (or the variable picker) to insert **ArticleURL** in place of the space between the quotes, so it becomes `{"url":"<ArticleURL>"}`. Make sure the result is valid JSON (one key `url`, value is the URL string).

7. **Save the response**  
   Add an action **Set Variable** after **Get Contents of URL**: name it e.g. `Response`, and set the value to **Contents of URL** (the output of the previous action).

### B.4 Show the result

1. Add an action **Show Result** (or **Show Notification** / **Show Alert**).
2. For the content, select the variable **Response** (so the API’s JSON reply is shown).

Optional: add an **If** condition that checks whether **Response** contains `"success":true` and then show different messages (e.g. “Saved to server” vs “Request failed” and the **Response** text).

### B.5 Name and save the shortcut

1. Tap the shortcut title at the top and give it a name, e.g. **TOKINDLE to EPUB**.
2. Optionally add an icon (tap the icon area).
3. Tap **Done** to save.

---

## Part C: Using the shortcut

1. In **WeChat**, open a public account article.
2. Tap **⋯** (top right) → **Copy Link** (or the equivalent that copies the article URL).
3. Run your Shortcut (**TOKINDLE to EPUB**):
   - If you used **Clipboard**: just run the shortcut; it will use the copied link.
   - If you used **Ask for Input**: when prompted, paste the link and confirm.
4. The shortcut will show the API response. On success you should see JSON like:
   ```json
   {"success": true, "path": "/some/path/output/Article Title.epub", "title": "Article Title"}
   ```
5. On the **Mac** where the backend runs, check the `output/` folder; the new `.epub` file should be there.

---

## Troubleshooting

| Problem | What to check |
|--------|----------------|
| “Could not connect” or timeout | iPhone and Mac on same Wi‑Fi? Server started with `--host 0.0.0.0`? URL is `http://MAC_IP:8000/parse-url`? Try opening `http://MAC_IP:8000/ping` in Safari on the phone. |
| 404 or “Not Found” | URL must end with `/parse-url` (no trailing slash after it). |
| 422 or error in response | Request body must be JSON: `{"url": "the_wechat_article_url"}`. Check that the variable (e.g. ArticleURL) is actually the link text. |
| Empty or wrong response | In “Get Contents of URL”, ensure Method is POST, header `Content-Type` is `application/json`, and Request Body is the JSON with `url`. |

---

## Optional: Using a tunnel (e.g. ngrok) for access from other networks

If you want to use the Shortcut when your iPhone is **not** on the same Wi‑Fi as the Mac (e.g. when away from home):

1. On the Mac, install and configure a tunneling tool (e.g. **ngrok**): sign up at [ngrok.com](https://ngrok.com), add your authtoken, then run `ngrok http 8000`.
2. Note the public URL ngrok gives you (e.g. `https://xxxx.ngrok-free.app`).
3. In your Shortcut, set the **URL** in “Get Contents of URL” to:  
   `https://YOUR_NGROK_URL/parse-url`  
   (e.g. `https://xxxx.ngrok-free.app/parse-url`).
4. Leave the **Method**, **Headers**, and **Request Body** as in B.3.

The backend can still run as before (`uvicorn main:app --reload --host 0.0.0.0 --port 8000` or just `uvicorn main:app --reload`); ngrok forwards traffic to port 8000. For day-to-day use on the same Wi‑Fi, the local IP URL is enough; use tunneling only when you need remote access.
