document.addEventListener("DOMContentLoaded", function () {
    const btn = document.getElementById("enable-notifications");
    if (!btn || !("serviceWorker" in navigator) || !("PushManager" in window)) {
        return;
    }

    const leagueSlug = btn.getAttribute("data-league-slug") || "";
    if (!leagueSlug) return;

    function urlBase64ToUint8Array(base64String) {
        const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
        const base64 = (base64String + padding)
            .replace(/-/g, "+")
            .replace(/_/g, "/");
        const rawData = atob(base64);
        const outputArray = new Uint8Array(rawData.length);
        for (let i = 0; i < rawData.length; i++) {
            outputArray[i] = rawData.charCodeAt(i);
        }
        return outputArray;
    }

    async function getPublicKey() {
        const resp = await fetch("/api/notifications/public-key");
        if (!resp.ok) return "";
        const data = await resp.json();
        return data.public_key || "";
    }

    async function subscribeNotifications() {
        try {
            const permission = await Notification.requestPermission();
            if (permission !== "granted") {
                alert("يجب السماح بالإشعارات من المتصفح أولاً.");
                return;
            }

            const publicKey = (await getPublicKey()).trim();
            if (!publicKey) {
                alert("الإشعارات غير مفعلة على الخادم (مفاتيح VAPID غير مضبوطة).");
                return;
            }

            // Unregister any old SWs that might conflict (e.g. /static/sw.js with scope /static/)
            const regs = await navigator.serviceWorker.getRegistrations();
            for (const r of regs) {
                if (r.scope.includes(location.origin) && r.active?.scriptURL !== location.origin + "/sw.js") {
                    await r.unregister();
                }
            }

            await navigator.serviceWorker.register("/sw.js");
            const registration = await navigator.serviceWorker.ready;
            const subscription = await registration.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: urlBase64ToUint8Array(publicKey),
            });

            const payload = {
                league_slug: leagueSlug,
                endpoint: subscription.endpoint,
                p256dh: subscription.toJSON().keys.p256dh,
                auth: subscription.toJSON().keys.auth,
            };

            const resp = await fetch("/api/notifications/subscribe", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            const data = await resp.json();
            if (!resp.ok || !data.success) {
                alert(data.detail || "تعذر تفعيل الإشعارات.");
                return;
            }
            alert("✅ تم تفعيل إشعارات الدوري بنجاح.");
        } catch (err) {
            console.error("Notification subscription error", err);
            const msg = err?.message || String(err);
            let hint = "";
            if (msg.toLowerCase().includes("push service error")) {
                hint =
                    "\n\n💡 جرّب:\n" +
                    "• متصفح Chrome على الكمبيوتر\n" +
                    "• إذا كنت على Brave: الإعدادات → الخصوصية → تفعيل «خدمات Google للإشعارات»\n" +
                    "• تأكد أن مفاتيح VAPID مضبوطة بشكل صحيح في Render";
            }
            alert("❌ حدث خطأ أثناء تفعيل الإشعارات.\n\n" + msg + hint);
        }
    }

    btn.addEventListener("click", subscribeNotifications);
});
