/**
 * ============================================================================
 *  AIStylistFlow.tsx — Main Orchestrator Component
 * ============================================================================
 *
 *  PURPOSE:
 *  Manages the 5-step "Zero-Friction, High-Data" user flow for the
 *  My Narrative AI Stylist. Renders each step sequentially with fluid
 *  transitions using Framer Motion.
 *
 *  STEPS:
 *  1. Intent & Vibe Selection (Occasion → Vibe Cards)
 *  2. "Magic Image" Upload (Drag & Drop)
 *  3. AI Generation Loading + Result (FLUX → Face Swap)
 *  4. Outfit Breakdown & Affiliate Upsell ("Switzerland" Monetization)
 *  5. Gamified Hooks (Mascot Quest + Style Graph)
 *
 *  TECH STACK:
 *  • React 18+ with TypeScript
 *  • Tailwind CSS for styling
 *  • Framer Motion for animations and Tinder-like swiping
 *  • Next.js App Router compatible
 *
 *  ANTI-HALLUCINATION GUARDRAILS:
 *  ✅ No recommendation algorithms — just state management + API calls
 *  ✅ All AI processing delegated to /api/stylist_pipeline backend
 *  ✅ Clean separation of concerns: UI ↔ State ↔ API
 *
 * ============================================================================
 */

"use client";

import React, { useState, useCallback, useRef, useEffect } from "react";
import { motion, AnimatePresence, PanInfo } from "framer-motion";
import VibeCardResult from "./VibeCardResult";

// ─────────────────────────────────────────────────────────────────────────────
// TYPE DEFINITIONS
// ─────────────────────────────────────────────────────────────────────────────

/** Occasion option for Step 1A */
interface Occasion {
    id: string;
    label: string;
    emoji: string;
    gradient: string; // Tailwind gradient classes
    description: string;
}

/** Vibe card for Step 1B (Tinder-like swiping) */
interface VibeCard {
    id: string;
    label: string;
    persona: string;
    emoji: string;
    gradient: string;
    tagline: string;
}

/** Pipeline response from the backend */
interface PipelineResponse {
    success: boolean;
    pipeline_duration_seconds: number;
    biometrics: {
        monk_skin_tone: number;
        mst_label: string;
        body_type: string;
        gender_presentation: string;
    };
    wardrobe: {
        items_detected: number;
        items: Array<{
            id: string;
            slot: string;
            category: string;
            sub_category: string;
            color: string;
            pattern: string;
            style: string;
            confidence: number;
            description: string;
        }>;
    };
    ghost_closet: {
        success: boolean;
        items_saved: number;
    };
    editorial: {
        flux_prompt: string;
        flux_image_url: string;
        final_image_url: string;
        occasion: { label: string };
        vibe: { label: string; style_persona: string };
    };
    color_theory: {
        mst_value: number;
        best_colors: string[];
        avoid_colors: string[];
        undertone_note: string;
        tooltip_text: string;
    };
    affiliate_upsells: Array<{
        product_name: string;
        brand: string;
        price: number;
        original_price: number;
        discount_pct: number;
        currency: string;
        affiliate_url: string;
        image_url: string;
        bank_offer: string;
        platform: string;
        gap_reason: string;
        gap_item: {
            description: string;
            is_owned: boolean;
        };
    }>;
    outfit_completion_pct: number;
    gamification: {
        mascot_quest: {
            cards_collected: number;
            cards_total: number;
            current_card: { name: string; rarity: string };
            next_card: { name: string; rarity: string; unlock_method: string };
            checkout_cta: string;
        };
        style_graph: {
            photos_uploaded: number;
            photos_required: number;
            progress_pct: number;
            reward_unlocked: boolean;
            reward_description: string;
        };
    };
}

/** The combined flow state passed between steps */
interface FlowState {
    occasion: string | null;
    vibeId: string | null;
    userImage: string | null; // Base64 encoded
    userImageFile: File | null;
    pipelineResult: PipelineResponse | null;
}

// ─────────────────────────────────────────────────────────────────────────────
// STATIC DATA — Occasions & Vibes
// ─────────────────────────────────────────────────────────────────────────────

const OCCASIONS: Occasion[] = [
    {
        id: "date_night",
        label: "Date Night",
        emoji: "🌙",
        gradient: "from-rose-500 via-pink-600 to-purple-700",
        description: "Romantic vibes, elevated style",
    },
    {
        id: "office",
        label: "Office",
        emoji: "💼",
        gradient: "from-slate-600 via-blue-700 to-indigo-800",
        description: "Sharp, smart, ready to lead",
    },
    {
        id: "sangeet",
        label: "Sangeet",
        emoji: "💃",
        gradient: "from-amber-500 via-orange-600 to-red-700",
        description: "Festive, bold, unapologetically desi",
    },
    {
        id: "airport_look",
        label: "Airport Look",
        emoji: "✈️",
        gradient: "from-cyan-500 via-teal-600 to-emerald-700",
        description: "Comfort that still serves looks",
    },
];

const VIBE_CARDS: VibeCard[] = [
    {
        id: "caffeine_survivor",
        label: "Surviving on Caffeine",
        persona: "Effortlessly unbothered",
        emoji: "☕",
        gradient: "from-amber-900 via-yellow-800 to-orange-900",
        tagline: "Too tired to care, too stylish to ignore",
    },
    {
        id: "sarcastic_rizzler",
        label: "The Sarcastic Rizzler",
        persona: "Sharp-witted trendsetter",
        emoji: "😏",
        gradient: "from-violet-700 via-purple-800 to-fuchsia-900",
        tagline: "Your outfit speaks before you do",
    },
    {
        id: "main_character",
        label: "Main Character Energy",
        persona: "Protagonist of every scene",
        emoji: "✨",
        gradient: "from-rose-600 via-pink-700 to-red-800",
        tagline: "The spotlight was built for you",
    },
    {
        id: "quiet_luxury",
        label: "Quiet Luxury",
        persona: "Old-money minimalist",
        emoji: "🤫",
        gradient: "from-stone-600 via-zinc-700 to-neutral-800",
        tagline: "If you know, you know",
    },
];

// ─────────────────────────────────────────────────────────────────────────────
// LOADING MESSAGES — Dopamine-building progression
// ─────────────────────────────────────────────────────────────────────────────

const LOADING_MESSAGES = [
    { text: "Analyzing Skin Tone...", emoji: "🎨", delay: 0 },
    { text: "Mapping Your Wardrobe...", emoji: "👔", delay: 1.5 },
    { text: "Detecting Body Proportions...", emoji: "📐", delay: 3 },
    { text: "Matching Color Theory...", emoji: "🌈", delay: 4.5 },
    { text: "Generating Editorial Look...", emoji: "📸", delay: 6 },
    { text: "Applying Your Identity...", emoji: "🪄", delay: 8 },
    { text: "Almost there...", emoji: "✨", delay: 10 },
];

// ─────────────────────────────────────────────────────────────────────────────
// ANIMATION VARIANTS
// ─────────────────────────────────────────────────────────────────────────────

const pageVariants = {
    enter: { opacity: 0, x: 80, scale: 0.95 },
    center: { opacity: 1, x: 0, scale: 1 },
    exit: { opacity: 0, x: -80, scale: 0.95 },
};

const pageTransition = {
    type: "spring",
    stiffness: 260,
    damping: 30,
};

const staggerContainer = {
    hidden: { opacity: 0 },
    show: {
        opacity: 1,
        transition: { staggerChildren: 0.1, delayChildren: 0.15 },
    },
};

const staggerItem = {
    hidden: { opacity: 0, y: 30, scale: 0.9 },
    show: { opacity: 1, y: 0, scale: 1, transition: { type: "spring", damping: 20 } },
};

// ─────────────────────────────────────────────────────────────────────────────
// COMPONENT: AIStylistFlow
// ─────────────────────────────────────────────────────────────────────────────

const AIStylistFlow: React.FC = () => {
    // ─── STATE ───
    const [currentStep, setCurrentStep] = useState<number>(1);
    const [subStep, setSubStep] = useState<"A" | "B">("A"); // For Step 1's two screens
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [showResultModal, setShowResultModal] = useState(false);

    const [flowState, setFlowState] = useState<FlowState>({
        occasion: null,
        vibeId: null,
        userImage: null,
        userImageFile: null,
        pipelineResult: null,
    });

    // Vibe card swipe state
    const [currentVibeIndex, setCurrentVibeIndex] = useState(0);
    const [swipeDirection, setSwipeDirection] = useState<string | null>(null);

    // File input ref
    const fileInputRef = useRef<HTMLInputElement>(null);

    // Drag state for upload zone
    const [isDragging, setIsDragging] = useState(false);

    // ─────────────────────────────────────────────────────────────────────────
    // API CALLS
    // ─────────────────────────────────────────────────────────────────────────

    /**
     * Backend API base URL.
     * In production, this would be your Vercel deployment URL.
     * For local development, use envvar or default to '/api'.
     */
    const API_BASE = process.env.NEXT_PUBLIC_API_URL || "/api";

    /**
     * Triggers the full pipeline: Biometrics + Wardrobe → FLUX → Face Swap
     * Called after Step 2 (image upload).
     */
    const runPipeline = useCallback(async () => {
        if (!flowState.occasion || !flowState.vibeId || !flowState.userImage) {
            setError("Missing required data. Please complete Steps 1 and 2.");
            return;
        }

        setIsLoading(true);
        setError(null);
        setCurrentStep(3); // Move to loading screen

        try {
            const response = await fetch(`${API_BASE}/stylist_pipeline`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    action: "full_pipeline",
                    user_id: "user_" + Date.now(), // In production, use real Shopify customer ID
                    occasion: flowState.occasion,
                    vibe_id: flowState.vibeId,
                    user_image: flowState.userImage,
                }),
            });

            const data: PipelineResponse = await response.json();

            if (!response.ok || !data.success) {
                throw new Error(data.error || "Pipeline failed. Please try again.");
            }

            setFlowState((prev) => ({ ...prev, pipelineResult: data }));
            setCurrentStep(4); // Move to results
        } catch (err: any) {
            console.error("Pipeline error:", err);
            setError(err.message || "Something went wrong. Please try again.");
            setCurrentStep(2); // Go back to upload step
        } finally {
            setIsLoading(false);
        }
    }, [flowState, API_BASE]);

    // ─────────────────────────────────────────────────────────────────────────
    // EVENT HANDLERS
    // ─────────────────────────────────────────────────────────────────────────

    /** Step 1A: Select occasion */
    const handleOccasionSelect = (occasionId: string) => {
        setFlowState((prev) => ({ ...prev, occasion: occasionId }));
        setSubStep("B"); // Transition to vibe selection
    };

    /** Step 1B: Swipe / select vibe card */
    const handleVibeSwipe = (direction: string, vibeId: string) => {
        setSwipeDirection(direction);

        if (direction === "right") {
            // RIGHT SWIPE = SELECT this vibe
            setFlowState((prev) => ({ ...prev, vibeId }));
            setTimeout(() => setCurrentStep(2), 400); // Brief visual feedback before transition
        } else {
            // LEFT SWIPE = SKIP to next card
            setTimeout(() => {
                setCurrentVibeIndex((prev) => Math.min(prev + 1, VIBE_CARDS.length - 1));
                setSwipeDirection(null);
            }, 300);
        }
    };

    /** Direct vibe selection via tap */
    const handleVibeSelect = (vibeId: string) => {
        setFlowState((prev) => ({ ...prev, vibeId }));
        setCurrentStep(2);
    };

    /** Step 2: Handle image drag events */
    const handleDragOver = (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragging(true);
    };

    const handleDragLeave = (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragging(false);
    };

    /** Step 2: Handle image drop */
    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragging(false);

        const files = e.dataTransfer.files;
        if (files.length > 0) {
            processImageFile(files[0]);
        }
    };

    /** Step 2: Handle file input change */
    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const files = e.target.files;
        if (files && files.length > 0) {
            processImageFile(files[0]);
        }
    };

    /** Process selected image → Base64, then trigger pipeline */
    const processImageFile = (file: File) => {
        if (!file.type.startsWith("image/")) {
            setError("Please upload an image file (JPG, PNG, or WebP).");
            return;
        }

        // Max 10MB
        if (file.size > 10 * 1024 * 1024) {
            setError("Image too large. Please upload an image under 10MB.");
            return;
        }

        setError(null);

        // Compress & convert to base64
        const reader = new FileReader();
        reader.onload = () => {
            const base64 = reader.result as string;
            setFlowState((prev) => ({
                ...prev,
                userImage: base64,
                userImageFile: file,
            }));

            // Automatically trigger the pipeline after upload
            // Small delay for visual feedback
            setTimeout(() => {
                runPipeline();
            }, 600);
        };
        reader.onerror = () => setError("Failed to read image. Please try again.");
        reader.readAsDataURL(file);
    };

    // After flowState is updated with userImage, trigger pipeline
    // (We use useEffect to handle the async state update)
    const [shouldRunPipeline, setShouldRunPipeline] = useState(false);

    useEffect(() => {
        if (shouldRunPipeline && flowState.userImage) {
            setShouldRunPipeline(false);
            runPipeline();
        }
    }, [shouldRunPipeline, flowState.userImage, runPipeline]);

    // Re-attach the processImageFile to use the flag instead
    const processImageFileWithPipeline = (file: File) => {
        if (!file.type.startsWith("image/")) {
            setError("Please upload an image file (JPG, PNG, or WebP).");
            return;
        }
        if (file.size > 10 * 1024 * 1024) {
            setError("Image too large. Please upload an image under 10MB.");
            return;
        }
        setError(null);

        const reader = new FileReader();
        reader.onload = () => {
            const base64 = reader.result as string;
            setFlowState((prev) => ({
                ...prev,
                userImage: base64,
                userImageFile: file,
            }));
            setShouldRunPipeline(true);
        };
        reader.onerror = () => setError("Failed to read image. Please try again.");
        reader.readAsDataURL(file);
    };

    // ─────────────────────────────────────────────────────────────────────────
    // RENDER: STEP 1A — Occasion Selector ("Where are we heading?")
    // ─────────────────────────────────────────────────────────────────────────

    const renderStep1A = () => (
        <motion.div
            key="step1a"
            variants={pageVariants}
            initial="enter"
            animate="center"
            exit="exit"
            transition={pageTransition}
            className="min-h-screen flex flex-col items-center justify-center px-4 py-8"
        >
            {/* Header */}
            <motion.div
                initial={{ opacity: 0, y: -30 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 }}
                className="text-center mb-12"
            >
                <h1 className="text-4xl md:text-5xl font-bold bg-gradient-to-r from-white via-purple-200 to-pink-200 bg-clip-text text-transparent mb-3">
                    Where are we heading?
                </h1>
                <p className="text-gray-400 text-lg">
                    Pick the scene. We'll style the look.
                </p>
            </motion.div>

            {/* Occasion Cards Grid */}
            <motion.div
                variants={staggerContainer}
                initial="hidden"
                animate="show"
                className="grid grid-cols-2 gap-4 md:gap-6 max-w-lg w-full"
            >
                {OCCASIONS.map((occ) => (
                    <motion.button
                        key={occ.id}
                        variants={staggerItem}
                        whileHover={{ scale: 1.05, y: -4 }}
                        whileTap={{ scale: 0.95 }}
                        onClick={() => handleOccasionSelect(occ.id)}
                        className={`
              relative overflow-hidden rounded-2xl p-6 md:p-8 
              bg-gradient-to-br ${occ.gradient}
              border border-white/10 backdrop-blur-sm
              shadow-2xl cursor-pointer group
              transition-all duration-300
              hover:border-white/30 hover:shadow-[0_0_40px_rgba(147,51,234,0.3)]
            `}
                    >
                        {/* Shimmer overlay on hover */}
                        <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent -translate-x-full group-hover:translate-x-full transition-transform duration-700" />

                        <span className="text-4xl md:text-5xl block mb-3">{occ.emoji}</span>
                        <span className="text-white font-bold text-lg md:text-xl block mb-1">
                            {occ.label}
                        </span>
                        <span className="text-white/60 text-sm block">
                            {occ.description}
                        </span>
                    </motion.button>
                ))}
            </motion.div>

            {/* Progress indicator */}
            <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.8 }}
                className="mt-10 flex items-center gap-2"
            >
                <div className="w-8 h-1.5 rounded-full bg-purple-500" />
                <div className="w-8 h-1.5 rounded-full bg-white/20" />
                <div className="w-8 h-1.5 rounded-full bg-white/20" />
                <div className="w-8 h-1.5 rounded-full bg-white/20" />
                <div className="w-8 h-1.5 rounded-full bg-white/20" />
            </motion.div>
        </motion.div>
    );

    // ─────────────────────────────────────────────────────────────────────────
    // RENDER: STEP 1B — Vibe Check (Tinder-like swipeable cards)
    // ─────────────────────────────────────────────────────────────────────────

    const renderStep1B = () => {
        const currentVibe = VIBE_CARDS[currentVibeIndex];
        const isLast = currentVibeIndex >= VIBE_CARDS.length - 1;

        return (
            <motion.div
                key="step1b"
                variants={pageVariants}
                initial="enter"
                animate="center"
                exit="exit"
                transition={pageTransition}
                className="min-h-screen flex flex-col items-center justify-center px-4 py-8"
            >
                {/* Header */}
                <motion.div
                    initial={{ opacity: 0, y: -20 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="text-center mb-8"
                >
                    <p className="text-purple-400 text-sm font-medium uppercase tracking-widest mb-2">
                        Vibe Check
                    </p>
                    <h2 className="text-3xl md:text-4xl font-bold text-white mb-2">
                        What's the energy today?
                    </h2>
                    <p className="text-gray-500 text-sm">
                        Swipe right to pick your vibe → or left to skip
                    </p>
                </motion.div>

                {/* Swipeable Card Stack */}
                <div className="relative w-full max-w-sm h-[420px]">
                    <AnimatePresence mode="popLayout">
                        {/* Background cards for depth effect */}
                        {VIBE_CARDS.slice(currentVibeIndex + 1, currentVibeIndex + 3)
                            .reverse()
                            .map((card, i) => (
                                <motion.div
                                    key={card.id + "-bg"}
                                    className={`absolute inset-0 rounded-3xl bg-gradient-to-br ${card.gradient} border border-white/5`}
                                    style={{
                                        zIndex: -i - 1,
                                        scale: 1 - (i + 1) * 0.05,
                                        y: (i + 1) * 8,
                                    }}
                                    initial={{ opacity: 0.5 }}
                                    animate={{ opacity: 0.3 }}
                                />
                            ))}

                        {/* Active card */}
                        <motion.div
                            key={currentVibe.id}
                            drag="x"
                            dragConstraints={{ left: 0, right: 0 }}
                            dragElastic={0.8}
                            onDragEnd={(_, info: PanInfo) => {
                                if (info.offset.x > 120) {
                                    handleVibeSwipe("right", currentVibe.id);
                                } else if (info.offset.x < -120) {
                                    handleVibeSwipe("left", currentVibe.id);
                                }
                            }}
                            initial={{ opacity: 0, scale: 0.8, rotateZ: 5 }}
                            animate={{
                                opacity: 1,
                                scale: 1,
                                rotateZ: 0,
                                x: swipeDirection === "right" ? 400 : swipeDirection === "left" ? -400 : 0,
                            }}
                            exit={{
                                opacity: 0,
                                scale: 0.5,
                                x: swipeDirection === "right" ? 500 : -500,
                                rotateZ: swipeDirection === "right" ? 20 : -20,
                            }}
                            transition={{ type: "spring", damping: 25, stiffness: 200 }}
                            className={`
                absolute inset-0 rounded-3xl 
                bg-gradient-to-br ${currentVibe.gradient}
                border border-white/20 backdrop-blur-xl
                shadow-[0_20px_60px_rgba(0,0,0,0.5)]
                cursor-grab active:cursor-grabbing
                flex flex-col items-center justify-center p-8
                select-none
              `}
                        >
                            {/* Floating shimmer particles */}
                            <div className="absolute inset-0 overflow-hidden rounded-3xl">
                                <div className="absolute top-1/4 left-1/4 w-32 h-32 bg-white/5 rounded-full blur-3xl animate-pulse" />
                                <div className="absolute bottom-1/3 right-1/4 w-24 h-24 bg-white/10 rounded-full blur-2xl animate-pulse" style={{ animationDelay: "1s" }} />
                            </div>

                            {/* Card content */}
                            <span className="text-7xl mb-6 relative z-10">{currentVibe.emoji}</span>
                            <h3 className="text-2xl md:text-3xl font-bold text-white text-center mb-2 relative z-10">
                                {currentVibe.label}
                            </h3>
                            <p className="text-white/70 text-center italic mb-4 relative z-10">
                                "{currentVibe.tagline}"
                            </p>
                            <span className="px-4 py-1.5 rounded-full bg-white/10 border border-white/20 text-white/80 text-sm relative z-10">
                                {currentVibe.persona}
                            </span>

                            {/* Swipe hint arrows */}
                            <div className="absolute bottom-6 left-0 right-0 flex justify-between px-6 relative z-10">
                                <span className="text-white/30 text-sm">← Skip</span>
                                <span className="text-green-400/60 text-sm font-medium">Choose →</span>
                            </div>
                        </motion.div>
                    </AnimatePresence>
                </div>

                {/* Direct selection buttons (alternative to swiping) */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.5 }}
                    className="mt-8 flex gap-3"
                >
                    <button
                        onClick={() => handleVibeSwipe("left", currentVibe.id)}
                        disabled={isLast}
                        className="px-5 py-2.5 rounded-xl bg-white/5 border border-white/10 text-gray-400 hover:bg-white/10 hover:text-white transition-all disabled:opacity-30"
                    >
                        ✕ Skip
                    </button>
                    <button
                        onClick={() => handleVibeSelect(currentVibe.id)}
                        className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-purple-600 to-pink-600 text-white font-medium hover:shadow-[0_0_30px_rgba(147,51,234,0.4)] transition-all"
                    >
                        ♥ This is me
                    </button>
                </motion.div>

                {/* Card counter */}
                <p className="mt-4 text-gray-600 text-xs">
                    {currentVibeIndex + 1} / {VIBE_CARDS.length}
                </p>

                {/* Progress indicator */}
                <div className="mt-6 flex items-center gap-2">
                    <div className="w-8 h-1.5 rounded-full bg-purple-500/50" />
                    <div className="w-8 h-1.5 rounded-full bg-purple-500" />
                    <div className="w-8 h-1.5 rounded-full bg-white/20" />
                    <div className="w-8 h-1.5 rounded-full bg-white/20" />
                    <div className="w-8 h-1.5 rounded-full bg-white/20" />
                </div>
            </motion.div>
        );
    };

    // ─────────────────────────────────────────────────────────────────────────
    // RENDER: STEP 2 — "Magic Image" Upload (Drag & Drop)
    // ─────────────────────────────────────────────────────────────────────────

    const renderStep2 = () => (
        <motion.div
            key="step2"
            variants={pageVariants}
            initial="enter"
            animate="center"
            exit="exit"
            transition={pageTransition}
            className="min-h-screen flex flex-col items-center justify-center px-4 py-8"
        >
            {/* Recap bar */}
            <motion.div
                initial={{ opacity: 0, y: -20 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex items-center gap-3 mb-8 px-5 py-3 rounded-2xl bg-white/5 border border-white/10 backdrop-blur-md"
            >
                <span className="text-sm text-gray-400">
                    {OCCASIONS.find((o) => o.id === flowState.occasion)?.emoji}{" "}
                    {OCCASIONS.find((o) => o.id === flowState.occasion)?.label}
                </span>
                <span className="text-white/20">→</span>
                <span className="text-sm text-purple-400">
                    {VIBE_CARDS.find((v) => v.id === flowState.vibeId)?.emoji}{" "}
                    {VIBE_CARDS.find((v) => v.id === flowState.vibeId)?.label}
                </span>
            </motion.div>

            {/* Header */}
            <motion.div
                initial={{ opacity: 0, y: -20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 }}
                className="text-center mb-10"
            >
                <h2 className="text-3xl md:text-4xl font-bold text-white mb-3">
                    Now, the magic photo ✨
                </h2>
                <p className="text-gray-400 text-base md:text-lg max-w-md mx-auto">
                    Upload a recent photo of yourself in a full outfit.
                    We'll extract your fit and generate your editorial look.
                </p>
            </motion.div>

            {/* Upload Zone */}
            <motion.div
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.4, type: "spring" }}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                className={`
          relative w-full max-w-md aspect-[3/4] rounded-3xl
          border-2 border-dashed cursor-pointer group
          flex flex-col items-center justify-center p-8
          transition-all duration-300
          ${isDragging
                        ? "border-purple-400 bg-purple-500/10 shadow-[0_0_60px_rgba(147,51,234,0.3)]"
                        : "border-white/20 bg-white/[0.02] hover:border-purple-500/50 hover:bg-purple-500/5"
                    }
        `}
            >
                {/* Animated border glow */}
                <div className={`
          absolute inset-0 rounded-3xl transition-opacity duration-500
          ${isDragging ? "opacity-100" : "opacity-0 group-hover:opacity-100"}
          bg-gradient-to-r from-purple-500/20 via-pink-500/20 to-purple-500/20
          blur-xl
        `} />

                {/* Upload icon */}
                <motion.div
                    animate={{
                        y: isDragging ? -8 : 0,
                        scale: isDragging ? 1.1 : 1,
                    }}
                    transition={{ type: "spring" }}
                    className="relative z-10 flex flex-col items-center"
                >
                    {flowState.userImage ? (
                        // Show preview if image is selected
                        <>
                            <img
                                src={flowState.userImage}
                                alt="Your uploaded photo"
                                className="w-48 h-64 object-cover rounded-2xl border border-white/20 shadow-2xl mb-4"
                            />
                            <p className="text-green-400 font-medium">✓ Photo ready</p>
                        </>
                    ) : (
                        // Show upload prompt
                        <>
                            <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-purple-500/20 to-pink-500/20 border border-white/10 flex items-center justify-center mb-6">
                                <svg
                                    className="w-10 h-10 text-purple-400"
                                    fill="none"
                                    viewBox="0 0 24 24"
                                    stroke="currentColor"
                                    strokeWidth={1.5}
                                >
                                    <path
                                        strokeLinecap="round"
                                        strokeLinejoin="round"
                                        d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"
                                    />
                                </svg>
                            </div>

                            <p className="text-white font-semibold text-lg mb-2 text-center">
                                Drop your photo here
                            </p>
                            <p className="text-gray-500 text-sm text-center">
                                or click to browse • Full outfit photo works best
                            </p>
                            <p className="text-gray-600 text-xs mt-3">
                                JPG, PNG, WebP • Max 10MB
                            </p>
                        </>
                    )}
                </motion.div>

                {/* Hidden file input */}
                <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    onChange={handleFileChange}
                    className="hidden"
                />
            </motion.div>

            {/* Error message */}
            {error && (
                <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="mt-4 px-5 py-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-sm max-w-md"
                >
                    ⚠ {error}
                </motion.div>
            )}

            {/* Progress indicator */}
            <div className="mt-10 flex items-center gap-2">
                <div className="w-8 h-1.5 rounded-full bg-purple-500/50" />
                <div className="w-8 h-1.5 rounded-full bg-purple-500/50" />
                <div className="w-8 h-1.5 rounded-full bg-purple-500" />
                <div className="w-8 h-1.5 rounded-full bg-white/20" />
                <div className="w-8 h-1.5 rounded-full bg-white/20" />
            </div>
        </motion.div>
    );

    // ─────────────────────────────────────────────────────────────────────────
    // RENDER: STEP 3 — Dopamine Loading Screen
    // ─────────────────────────────────────────────────────────────────────────

    const renderStep3Loading = () => (
        <motion.div
            key="step3"
            variants={pageVariants}
            initial="enter"
            animate="center"
            exit="exit"
            transition={pageTransition}
            className="min-h-screen flex flex-col items-center justify-center px-4 py-8"
        >
            {/* Central pulsing orb */}
            <motion.div
                className="relative mb-12"
                animate={{ scale: [1, 1.1, 1], opacity: [0.8, 1, 0.8] }}
                transition={{ duration: 2, repeat: Infinity }}
            >
                <div className="w-32 h-32 rounded-full bg-gradient-to-br from-purple-600 via-pink-500 to-orange-500 blur-2xl opacity-50" />
                <div className="absolute inset-4 rounded-full bg-gradient-to-br from-purple-500 to-pink-600 flex items-center justify-center">
                    <motion.span
                        className="text-4xl"
                        animate={{ rotateY: [0, 360] }}
                        transition={{ duration: 3, repeat: Infinity, ease: "linear" }}
                    >
                        🪄
                    </motion.span>
                </div>
            </motion.div>

            {/* Progressive loading messages */}
            <div className="space-y-3 max-w-sm w-full">
                {LOADING_MESSAGES.map((msg, i) => (
                    <motion.div
                        key={i}
                        initial={{ opacity: 0, x: -20 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: msg.delay, duration: 0.5 }}
                        className="flex items-center gap-3 px-5 py-3 rounded-xl bg-white/5 border border-white/5"
                    >
                        <span className="text-lg">{msg.emoji}</span>
                        <span className="text-gray-300 text-sm font-medium">{msg.text}</span>
                        <motion.div
                            initial={{ width: 0 }}
                            animate={{ width: "100%" }}
                            transition={{ delay: msg.delay + 0.3, duration: 1.5 }}
                            className="flex-1 h-0.5 rounded-full bg-gradient-to-r from-purple-500 to-pink-500"
                        />
                    </motion.div>
                ))}
            </div>

            {/* Subtle progress bar at bottom */}
            <motion.div
                className="mt-12 w-64 h-1 rounded-full bg-white/10 overflow-hidden"
            >
                <motion.div
                    className="h-full bg-gradient-to-r from-purple-500 via-pink-500 to-orange-500"
                    initial={{ width: "0%" }}
                    animate={{ width: "100%" }}
                    transition={{ duration: 12, ease: "easeInOut" }}
                />
            </motion.div>
        </motion.div>
    );

    // ─────────────────────────────────────────────────────────────────────────
    // RENDER: STEP 4 — Results + Outfit Breakdown + Upsells
    // (Delegates to VibeCardResult component)
    // ─────────────────────────────────────────────────────────────────────────

    const renderStep4 = () => {
        if (!flowState.pipelineResult) return null;

        return (
            <motion.div
                key="step4"
                variants={pageVariants}
                initial="enter"
                animate="center"
                exit="exit"
                transition={pageTransition}
                className="min-h-screen py-8 px-4"
            >
                <VibeCardResult
                    result={flowState.pipelineResult}
                    onShowGamification={() => setShowResultModal(true)}
                />

                {/* Progress indicator */}
                <div className="flex items-center justify-center gap-2 mt-8">
                    <div className="w-8 h-1.5 rounded-full bg-purple-500/50" />
                    <div className="w-8 h-1.5 rounded-full bg-purple-500/50" />
                    <div className="w-8 h-1.5 rounded-full bg-purple-500/50" />
                    <div className="w-8 h-1.5 rounded-full bg-purple-500" />
                    <div className="w-8 h-1.5 rounded-full bg-white/20" />
                </div>
            </motion.div>
        );
    };

    // ─────────────────────────────────────────────────────────────────────────
    // RENDER: STEP 5 — Gamified Hooks Modal
    // ─────────────────────────────────────────────────────────────────────────

    const renderStep5Modal = () => {
        if (!flowState.pipelineResult) return null;
        const { gamification } = flowState.pipelineResult;

        return (
            <AnimatePresence>
                {showResultModal && (
                    <>
                        {/* Backdrop */}
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            onClick={() => setShowResultModal(false)}
                            className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50"
                        />

                        {/* Modal */}
                        <motion.div
                            initial={{ opacity: 0, y: 100, scale: 0.95 }}
                            animate={{ opacity: 1, y: 0, scale: 1 }}
                            exit={{ opacity: 0, y: 100, scale: 0.95 }}
                            transition={{ type: "spring", damping: 25 }}
                            className="fixed bottom-0 inset-x-0 z-50 max-h-[85vh] overflow-y-auto
                         bg-gradient-to-b from-gray-900 to-black 
                         rounded-t-3xl border-t border-white/10
                         px-6 py-8 pb-safe"
                        >
                            {/* Drag handle */}
                            <div className="w-12 h-1 rounded-full bg-white/20 mx-auto mb-8" />

                            {/* ─── COMPONENT 1: Mascot Quest ─── */}
                            <div className="mb-8">
                                <h3 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
                                    🎴 Mascot Quest
                                </h3>

                                {/* Progress bar */}
                                <div className="relative w-full h-3 rounded-full bg-white/10 overflow-hidden mb-3">
                                    <motion.div
                                        initial={{ width: 0 }}
                                        animate={{
                                            width: `${(gamification.mascot_quest.cards_collected / gamification.mascot_quest.cards_total) * 100}%`,
                                        }}
                                        transition={{ delay: 0.5, duration: 1, ease: "easeOut" }}
                                        className="h-full bg-gradient-to-r from-yellow-500 via-orange-500 to-red-500 rounded-full"
                                    />
                                </div>

                                <p className="text-gray-400 text-sm mb-4">
                                    <span className="text-white font-bold">
                                        {gamification.mascot_quest.cards_collected}/{gamification.mascot_quest.cards_total}
                                    </span>{" "}
                                    Mascot Cards Collected
                                </p>

                                {/* Current card */}
                                <div className="flex gap-4 mb-4">
                                    <div className="w-16 h-20 rounded-xl bg-gradient-to-br from-yellow-600 to-orange-700 border border-yellow-500/30 flex items-center justify-center shadow-lg">
                                        <span className="text-3xl">🃏</span>
                                    </div>
                                    <div>
                                        <p className="text-white font-medium">
                                            {gamification.mascot_quest.current_card.name}
                                        </p>
                                        <p className="text-yellow-500 text-xs font-medium">
                                            {gamification.mascot_quest.current_card.rarity}
                                        </p>
                                    </div>
                                </div>

                                {/* Next card unlock CTA */}
                                <div className="rounded-2xl bg-gradient-to-r from-purple-500/10 to-pink-500/10 border border-purple-500/20 p-4">
                                    <p className="text-gray-300 text-sm mb-3">
                                        🔮 Next: <span className="text-purple-400 font-medium">{gamification.mascot_quest.next_card.name}</span>
                                        <span className="text-purple-500/60 text-xs ml-2">({gamification.mascot_quest.next_card.rarity})</span>
                                    </p>
                                    <button className="w-full py-3 rounded-xl bg-gradient-to-r from-purple-600 to-pink-600 text-white font-semibold text-sm hover:shadow-[0_0_30px_rgba(147,51,234,0.4)] transition-all active:scale-95">
                                        {gamification.mascot_quest.checkout_cta}
                                    </button>
                                </div>
                            </div>

                            {/* Divider */}
                            <div className="w-full h-px bg-gradient-to-r from-transparent via-white/10 to-transparent my-6" />

                            {/* ─── COMPONENT 2: Style Graph Builder ─── */}
                            <div>
                                <h3 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
                                    📊 Style Graph Builder
                                </h3>

                                {/* Circular progress */}
                                <div className="flex items-center gap-6 mb-4">
                                    <div className="relative w-20 h-20">
                                        <svg className="w-20 h-20 -rotate-90" viewBox="0 0 36 36">
                                            <circle
                                                cx="18" cy="18" r="16"
                                                fill="none"
                                                stroke="rgba(255,255,255,0.1)"
                                                strokeWidth="2"
                                            />
                                            <motion.circle
                                                cx="18" cy="18" r="16"
                                                fill="none"
                                                stroke="url(#progressGradient)"
                                                strokeWidth="2"
                                                strokeLinecap="round"
                                                strokeDasharray={`${gamification.style_graph.progress_pct} 100`}
                                                initial={{ strokeDasharray: "0 100" }}
                                                animate={{ strokeDasharray: `${gamification.style_graph.progress_pct} 100` }}
                                                transition={{ delay: 0.5, duration: 1.5, ease: "easeOut" }}
                                            />
                                            <defs>
                                                <linearGradient id="progressGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                                                    <stop offset="0%" stopColor="#a855f7" />
                                                    <stop offset="100%" stopColor="#ec4899" />
                                                </linearGradient>
                                            </defs>
                                        </svg>
                                        <span className="absolute inset-0 flex items-center justify-center text-white font-bold text-sm">
                                            {gamification.style_graph.progress_pct}%
                                        </span>
                                    </div>

                                    <div>
                                        <p className="text-white font-medium mb-1">
                                            {gamification.style_graph.photos_uploaded} / {gamification.style_graph.photos_required} Photos
                                        </p>
                                        <p className="text-gray-500 text-sm">
                                            Upload {gamification.style_graph.photos_required - gamification.style_graph.photos_uploaded} more to unlock reward
                                        </p>
                                    </div>
                                </div>

                                {/* Upload CTA */}
                                <button className="w-full py-4 rounded-2xl bg-gradient-to-r from-emerald-600/20 to-teal-600/20 border border-emerald-500/30 text-emerald-400 font-medium text-sm hover:bg-emerald-500/20 hover:border-emerald-400/40 transition-all flex items-center justify-center gap-2 active:scale-95">
                                    📸 Upload 3 more OOTD photos to train your AI and unlock 5% Store Credit
                                </button>

                                {/* Reward preview */}
                                <div className="mt-4 flex items-center gap-3 px-4 py-3 rounded-xl bg-white/5 border border-white/5">
                                    <span className="text-2xl">🎁</span>
                                    <div>
                                        <p className="text-white text-sm font-medium">Reward: {gamification.style_graph.credit_amount} Store Credit</p>
                                        <p className="text-gray-500 text-xs">Unlocks after {gamification.style_graph.photos_required} OOTD uploads</p>
                                    </div>
                                </div>
                            </div>

                            {/* Close button */}
                            <button
                                onClick={() => setShowResultModal(false)}
                                className="mt-8 w-full py-3 rounded-xl bg-white/5 border border-white/10 text-gray-400 text-sm hover:bg-white/10 transition-all"
                            >
                                Close
                            </button>
                        </motion.div>
                    </>
                )}
            </AnimatePresence>
        );
    };

    // ─────────────────────────────────────────────────────────────────────────
    // MAIN RENDER
    // ─────────────────────────────────────────────────────────────────────────

    return (
        <div className="min-h-screen bg-gradient-to-b from-[#0a0a0f] via-[#0d0d1a] to-[#0a0a0f] text-white overflow-hidden">
            {/* Ambient background effects */}
            <div className="fixed inset-0 pointer-events-none z-0">
                <div className="absolute top-0 left-1/4 w-96 h-96 bg-purple-900/10 rounded-full blur-[120px]" />
                <div className="absolute bottom-1/4 right-1/4 w-80 h-80 bg-pink-900/10 rounded-full blur-[100px]" />
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-indigo-900/5 rounded-full blur-[150px]" />
            </div>

            {/* Main content */}
            <div className="relative z-10">
                <AnimatePresence mode="wait">
                    {/* Step 1: Occasion + Vibe */}
                    {currentStep === 1 && subStep === "A" && renderStep1A()}
                    {currentStep === 1 && subStep === "B" && renderStep1B()}

                    {/* Step 2: Image Upload */}
                    {currentStep === 2 && renderStep2()}

                    {/* Step 3: Loading */}
                    {currentStep === 3 && isLoading && renderStep3Loading()}

                    {/* Step 4: Results (VibeCardResult) */}
                    {currentStep === 4 && renderStep4()}
                </AnimatePresence>

                {/* Step 5: Gamification Modal (overlays on top of Step 4) */}
                {renderStep5Modal()}
            </div>
        </div>
    );
};

export default AIStylistFlow;
