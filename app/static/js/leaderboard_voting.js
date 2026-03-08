document.addEventListener("DOMContentLoaded", function () {
    const configElement = document.getElementById("voting-config");
    const modal = document.getElementById("voting-modal");
    if (!configElement || !modal) return;

    const config = configElement.dataset;
    let currentMatchId = config.matchId !== "null" ? parseInt(config.matchId, 10) : null;
    let currentRound = parseInt(config.round, 10) || 0;
    let currentVoterId = null;
    let currentCandidateId = null;
    let livePollingInterval = null;

    const liveSection = document.getElementById("voting-live-results");
    const liveBody = document.getElementById("voting-live-body");
    const liveMeta = document.getElementById("voting-live-meta");
    const step1 = document.getElementById("voting-step-1");
    const step2 = document.getElementById("voting-step-2");
    const voterList = document.getElementById("voter-list");
    const candidateList = document.getElementById("candidate-list");
    const submitBtn = document.getElementById("submit-vote-btn");
    const closeBtn = document.getElementById("close-voting-modal-btn");

    async function generateFingerprint() {
        const components = [
            screen.width,
            screen.height,
            screen.colorDepth,
            navigator.language,
            Intl.DateTimeFormat().resolvedOptions().timeZone,
            navigator.userAgent,
            navigator.hardwareConcurrency || "",
            navigator.platform || "",
        ];
        try {
            const canvas = document.createElement("canvas");
            const ctx = canvas.getContext("2d");
            if (ctx) {
                ctx.textBaseline = "top";
                ctx.font = "14px Arial";
                ctx.fillText("fp_probe", 2, 2);
                components.push(canvas.toDataURL().slice(-50));
            }
        } catch (e) {
            console.error("Fingerprint canvas failed", e);
        }
        const raw = components.join("|");
        const encoded = new TextEncoder().encode(raw);
        const hashBuf = await crypto.subtle.digest("SHA-256", encoded);
        return Array.from(new Uint8Array(hashBuf))
            .map((b) => b.toString(16).padStart(2, "0"))
            .join("");
    }

    function voteStorageKey() {
        return `voted_${currentMatchId}_${currentRound}`;
    }

    function stopLivePolling() {
        if (livePollingInterval) {
            clearInterval(livePollingInterval);
            livePollingInterval = null;
        }
    }

    function resetVotingSteps() {
        currentVoterId = null;
        currentCandidateId = null;
        if (step1) step1.style.display = "block";
        if (step2) step2.style.display = "none";
        if (submitBtn) submitBtn.style.display = "none";
        document.querySelectorAll(".player-card").forEach((c) => c.classList.remove("selected"));
    }

    async function selectVoter(cardEl) {
        const id = parseInt(cardEl.getAttribute("data-id"), 10);
        if (!id) return;
        currentVoterId = id;

        document.querySelectorAll("#voter-list .player-card").forEach((c) => c.classList.remove("selected"));
        cardEl.classList.add("selected");

        if (step1) step1.style.display = "none";
        if (step2) step2.style.display = "block";

        let excludedIds = [];
        try {
            const res = await fetch(`/api/voting/match/${currentMatchId}/status?voter_id=${id}`);
            if (res.ok) {
                const data = await res.json();
                excludedIds = Array.isArray(data.excluded_player_ids) ? data.excluded_player_ids : [];
            }
        } catch (e) {
            console.error("Failed to fetch voting status for excluded players", e);
        }

        document.querySelectorAll(".candidate-card").forEach((card) => {
            const candidateId = parseInt(card.getAttribute("data-id"), 10);
            const isSelf = candidateId === id;
            const isPreviousWinner = excludedIds.indexOf(candidateId) !== -1;
            card.style.display = isSelf || isPreviousWinner ? "none" : "flex";
            card.classList.toggle("excluded", isPreviousWinner);
        });
    }

    function selectCandidate(cardEl) {
        const id = parseInt(cardEl.getAttribute("data-id"), 10);
        if (!id) return;
        currentCandidateId = id;
        document.querySelectorAll("#candidate-list .player-card").forEach((c) => c.classList.remove("selected"));
        cardEl.classList.add("selected");
        if (submitBtn) submitBtn.style.display = "inline-block";
    }

    function closeVotingModal() {
        modal.style.display = "none";
        modal.classList.remove("active");
        stopLivePolling();
    }

    async function openVotingModal(matchId) {
        const effectiveMatchId = matchId ?? currentMatchId;
        if (!effectiveMatchId) {
            if (typeof showToast !== "undefined") {
                showToast("في مشكلة في تحديد رقم الماتش للتصويت. رجاءً حدّث الصفحة وحاول تاني.", "error");
            } else {
                alert("في مشكلة في تحديد رقم الماتش للتصويت. رجاءً حدّث الصفحة وحاول تاني.");
            }
            return;
        }

        currentMatchId = parseInt(effectiveMatchId, 10);

        try {
            const res = await fetch(`/api/voting/match/${currentMatchId}/live`);
            if (res.ok) {
                const data = await res.json();
                const serverRound = parseInt(data.round_number, 10) || 0;
                currentRound = serverRound;
                const roundNumEl = document.getElementById("round-num");
                if (roundNumEl) roundNumEl.textContent = String(currentRound);

                const key = voteStorageKey();
                const existingVote = typeof localStorage !== "undefined" ? localStorage.getItem(key) : null;
                if (existingVote) {
                    if (typeof showToast !== "undefined") {
                        showToast("يا غشاش يا حرامي يا وسخ! 🤡 شكلك كنت صوّت قبل كده – السيرفر هيقرر.", "error");
                    } else {
                        alert("يا غشاش يا حرامي يا وسخ! 🤡 شكلك كنت صوّت قبل كده – السيرفر هيقرر.");
                    }
                }
            }
        } catch (e) {
            console.error("Failed to fetch voting round or check vote:", e);
        }

        modal.style.display = "flex";
        modal.classList.add("active");
        resetVotingSteps();
        startLivePolling();
    }

    function startLivePolling() {
        if (!currentMatchId || !liveSection || !liveBody || !liveMeta) return;
        liveSection.style.display = "block";

        const fetchLive = async () => {
            try {
                const res = await fetch(`/api/voting/match/${currentMatchId}/live`);
                if (!res.ok) {
                    if (res.status === 404) {
                        liveSection.style.display = "none";
                    }
                    return;
                }
                const data = await res.json();
                const totalVotes = data.total_votes || 0;
                const isClosed = !data.is_open;
                const rows = Array.isArray(data.candidates) ? data.candidates : [];

                liveBody.innerHTML = "";
                if (totalVotes === 0) {
                    liveMeta.textContent = "لا توجد أصوات حتى الآن. كن أول من يصوّت!";
                } else {
                    liveMeta.textContent = `إجمالي الأصوات: ${totalVotes}`;
                    const maxVotes = rows.reduce((max, row) => Math.max(max, row.votes || 0), 0);
                    rows.forEach((row) => {
                        const percent = typeof row.percent === "number"
                            ? row.percent.toFixed(1)
                            : (totalVotes > 0 ? ((row.votes / totalVotes) * 100).toFixed(1) : "0.0");

                        const tr = document.createElement("tr");
                        if (maxVotes > 0 && row.votes === maxVotes) {
                            tr.classList.add("highlight-row");
                        }

                        const nameCell = document.createElement("td");
                        nameCell.textContent = row.name;
                        const votesCell = document.createElement("td");
                        votesCell.textContent = String(row.votes);
                        const percentCell = document.createElement("td");
                        percentCell.textContent = `${percent}%`;

                        tr.appendChild(nameCell);
                        tr.appendChild(votesCell);
                        tr.appendChild(percentCell);
                        liveBody.appendChild(tr);
                    });
                }

                if (isClosed) {
                    stopLivePolling();
                    liveMeta.textContent += " · تم إغلاق التصويت لهذه المباراة.";
                }
            } catch (e) {
                console.error("Error fetching live voting results", e);
            }
        };

        fetchLive();
        stopLivePolling();
        livePollingInterval = setInterval(fetchLive, 5000);
    }

    async function submitVote() {
        if (!currentVoterId || !currentCandidateId || !currentMatchId || !submitBtn) return;

        submitBtn.disabled = true;
        submitBtn.classList.add("btn-loading");
        const originalText = submitBtn.textContent;
        submitBtn.textContent = "جاري الإرسال...";

        try {
            const fp = await generateFingerprint();
            const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute("content") || "";
            const response = await fetch("/api/voting/vote", {
                method: "POST",
                headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
                body: JSON.stringify({
                    match_id: currentMatchId,
                    round_number: currentRound,
                    voter_id: currentVoterId,
                    candidate_id: currentCandidateId,
                    device_fingerprint: fp,
                }),
            });

            const result = await response.json();
            if (response.ok) {
                localStorage.setItem(voteStorageKey(), "1");
                if (typeof showToast !== "undefined") {
                    showToast("تم تسجيل تصويتك بنجاح!", "success");
                } else {
                    alert("تم تسجيل تصويتك بنجاح!");
                }
                startLivePolling();
                return;
            }

            if (typeof showToast !== "undefined") {
                showToast(result.detail || "حدث خطأ.", "error");
            } else {
                alert(result.detail || "حدث خطأ.");
            }
            submitBtn.disabled = false;
            submitBtn.classList.remove("btn-loading");
            submitBtn.textContent = "إرسال التصويت 🚀";
        } catch (error) {
            console.error("Error:", error);
            if (typeof showToast !== "undefined") {
                showToast("حدث خطأ في الاتصال.", "error");
            }
            submitBtn.disabled = false;
            submitBtn.classList.remove("btn-loading");
            submitBtn.textContent = "إرسال التصويت 🚀";
        }
    }

    document.querySelectorAll(".open-voting-modal-btn").forEach((btn) => {
        btn.addEventListener("click", function (e) {
            e.preventDefault();
            openVotingModal(this.getAttribute("data-match-id"));
        });
    });

    if (closeBtn) {
        closeBtn.addEventListener("click", closeVotingModal);
    }

    if (submitBtn) {
        submitBtn.addEventListener("click", submitVote);
    }

    if (voterList) {
        voterList.addEventListener("click", function (e) {
            const card = e.target.closest(".player-card");
            if (!card) return;
            selectVoter(card);
        });
    }

    if (candidateList) {
        candidateList.addEventListener("click", function (e) {
            const card = e.target.closest(".candidate-card");
            if (!card || card.style.display === "none") return;
            selectCandidate(card);
        });
    }
});
