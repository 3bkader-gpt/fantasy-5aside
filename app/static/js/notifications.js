document.addEventListener("DOMContentLoaded", function () {
    const btn = document.getElementById("enable-notifications");
    if (!btn || !("serviceWorker" in navigator) || !("PushManager" in window)) {
        return;
    }

    const leagueSlug = btn.getAttribute("data-league-slug") || "";
    if (!leagueSlug) return;

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

            const registration = await navigator.serviceWorker.register("/static/sw.js", { scope: "/" });
            await navigator.serviceWorker.ready;
            const subscription = await registration.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: Uint8Array.from(
                    atob(publicKey.replace(/_/g, "/").replace(/-/g, "+").replace(/\s/g, "")),
                    (c) => c.charCodeAt(0)
                ),
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
            alert("❌ حدث خطأ أثناء تفعيل الإشعارات.\n\n" + msg);
        }
    }

    btn.addEventListener("click", subscribeNotifications);
});
