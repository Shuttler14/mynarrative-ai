/**
 * ============================================================================
 *  VibeCardResult.tsx — Editorial Result + Upsell Component
 * ============================================================================
 *
 *  PURPOSE:
 *  Renders the final AI-generated editorial image (post Face Swap) along with:
 *  1. The main "Vibe Card" showing the generated look
 *  2. A "Why This Works" tooltip explaining Monk Skin Tone color theory
 *  3. The Outfit Breakdown showing owned vs. gap items
 *  4. The "Switzerland" Affiliate Upsell box for gap items (RED highlight)
 *
 *  TECH STACK:
 *  • React 18+ with TypeScript
 *  • Tailwind CSS for styling
 *  • Framer Motion for micro-animations and tooltip reveal
 *
 *  ANTI-HALLUCINATION GUARDRAILS:
 *  ✅ No web scraping — affiliate data comes from mock API
 *  ✅ No image processing — all data pre-computed by backend
 *  ✅ Clean presentational component — no business logic
 *
 * ============================================================================
 */

"use client";

import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

// ─────────────────────────────────────────────────────────────────────────────
// TYPE DEFINITIONS (matches backend PipelineResponse shape)
// ─────────────────────────────────────────────────────────────────────────────

interface WardrobeItem {
    id: string;
    slot: string;
    category: string;
    sub_category: string;
    color: string;
    pattern: string;
    style: string;
    confidence: number;
    description: string;
}

interface AffiliateUpsell {
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
    style_context: string;
    gap_item: {
        description: string;
        is_owned: boolean;
    };
}

interface PipelineResult {
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
        items: WardrobeItem[];
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
    affiliate_upsells: AffiliateUpsell[];
    outfit_completion_pct: number;
    gamification: {
        mascot_quest: {
            cards_collected: number;
            cards_total: number;
            checkout_cta: string;
        };
        style_graph: {
            progress_pct: number;
            reward_description: string;
        };
    };
}

interface VibeCardResultProps {
    result: PipelineResult;
    onShowGamification: () => void;
}

// ─────────────────────────────────────────────────────────────────────────────
// SLOT ICON MAPPING
// ─────────────────────────────────────────────────────────────────────────────

const SLOT_ICONS: Record<string, string> = {
    top: "👕",
    bottom: "👖",
    footwear: "👟",
    accessory: "⌚",
    sneakers: "👟",
    sunglasses: "🕶️",
    blazer: "🧥",
    watch: "⌚",
    ethnic_kurta: "🥻",
};

// ─────────────────────────────────────────────────────────────────────────────
// COMPONENT: VibeCardResult
// ─────────────────────────────────────────────────────────────────────────────

const VibeCardResult: React.FC<VibeCardResultProps> = ({
    result,
    onShowGamification,
}) => {
    // ─── STATE ───
    const [showColorTheory, setShowColorTheory] = useState(false);
    const [expandedUpsell, setExpandedUpsell] = useState<number | null>(null);
    const [imageLoaded, setImageLoaded] = useState(false);

    const {
        editorial,
        color_theory,
        wardrobe,
        affiliate_upsells,
        outfit_completion_pct,
        biometrics,
        gamification,
    } = result;

    // ─────────────────────────────────────────────────────────────────────────
    // RENDER: Main Editorial Vibe Card
    // ─────────────────────────────────────────────────────────────────────────

    return (
        <div className="flex flex-col items-center w-full max-w-lg mx-auto">
            {/* ─── SECTION 1: Editorial Image Card ─── */}
            <motion.div
                initial={{ opacity: 0, y: 40, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                transition={{ type: "spring", damping: 20, delay: 0.2 }}
                className="w-full relative"
            >
                {/* Magazine-style header */}
                <motion.div
                    initial={{ opacity: 0, y: -20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.4 }}
                    className="text-center mb-6"
                >
                    <p className="text-purple-400 text-xs font-medium uppercase tracking-[0.3em] mb-1">
                        Your Narrative
                    </p>
                    <h2 className="text-3xl md:text-4xl font-bold bg-gradient-to-r from-white via-purple-200 to-pink-200 bg-clip-text text-transparent">
                        Editorial Look
                    </h2>
                </motion.div>

                {/* Image container */}
                <div className="relative rounded-3xl overflow-hidden shadow-[0_20px_80px_rgba(147,51,234,0.15)] border border-white/10 group">
                    {/* Loading skeleton */}
                    {!imageLoaded && (
                        <div className="w-full aspect-[3/4] bg-gradient-to-br from-purple-900/20 to-pink-900/20 animate-pulse flex items-center justify-center">
                            <motion.span
                                animate={{ rotate: 360 }}
                                transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
                                className="text-4xl"
                            >
                                ✨
                            </motion.span>
                        </div>
                    )}

                    {/* Generated image */}
                    <img
                        src={editorial.final_image_url}
                        alt={`AI-generated ${editorial.vibe?.label || "editorial"} look`}
                        className={`w-full aspect-[3/4] object-cover transition-opacity duration-700 ${imageLoaded ? "opacity-100" : "opacity-0 absolute"}`}
                        onLoad={() => setImageLoaded(true)}
                    />

                    {/* Overlay gradients */}
                    <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent" />

                    {/* Bottom info bar on image */}
                    <div className="absolute bottom-0 left-0 right-0 p-5">
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-white font-bold text-lg leading-tight">
                                    {editorial.vibe?.label || "Your Look"}
                                </p>
                                <p className="text-white/60 text-sm">
                                    {editorial.occasion?.label || "Editorial"} • {editorial.vibe?.style_persona || ""}
                                </p>
                            </div>

                            {/* Completion badge */}
                            <div className={`
                px-3 py-1.5 rounded-full text-xs font-bold
                ${outfit_completion_pct >= 90
                                    ? "bg-green-500/20 border border-green-500/40 text-green-400"
                                    : "bg-red-500/20 border border-red-500/40 text-red-400"
                                }
              `}>
                                {outfit_completion_pct}% Complete
                            </div>
                        </div>
                    </div>

                    {/* MST badge — top right corner */}
                    <motion.button
                        whileHover={{ scale: 1.05 }}
                        whileTap={{ scale: 0.95 }}
                        onClick={() => setShowColorTheory(!showColorTheory)}
                        className="absolute top-4 right-4 px-3 py-2 rounded-xl bg-black/50 backdrop-blur-md border border-white/20 cursor-pointer group/tooltip"
                    >
                        <span className="text-xs text-white/80">
                            MST {color_theory.mst_value} •{" "}
                            <span className="text-purple-400">Why this works</span> ↗
                        </span>
                    </motion.button>
                </div>
            </motion.div>

            {/* ─── SECTION 2: "Why This Works" Color Theory Tooltip ─── */}
            <AnimatePresence>
                {showColorTheory && (
                    <motion.div
                        initial={{ opacity: 0, height: 0, marginTop: 0 }}
                        animate={{ opacity: 1, height: "auto", marginTop: 16 }}
                        exit={{ opacity: 0, height: 0, marginTop: 0 }}
                        transition={{ type: "spring", damping: 25 }}
                        className="w-full overflow-hidden"
                    >
                        <div className="rounded-2xl bg-gradient-to-br from-purple-500/10 via-pink-500/5 to-transparent border border-purple-500/20 p-5">
                            <div className="flex items-start gap-3 mb-4">
                                <span className="text-2xl mt-0.5">🎨</span>
                                <div>
                                    <h4 className="text-white font-semibold text-sm mb-1">
                                        Color Theory — Monk Skin Tone {color_theory.mst_value}
                                    </h4>
                                    <p className="text-gray-400 text-xs leading-relaxed">
                                        {color_theory.tooltip_text}
                                    </p>
                                </div>
                            </div>

                            {/* Best colors */}
                            <div className="mb-3">
                                <p className="text-gray-500 text-xs font-medium uppercase tracking-wider mb-2">
                                    ✓ Best Colors for You
                                </p>
                                <div className="flex flex-wrap gap-2">
                                    {color_theory.best_colors.map((color, i) => (
                                        <span
                                            key={i}
                                            className="px-3 py-1 rounded-full bg-green-500/10 border border-green-500/30 text-green-400 text-xs font-medium"
                                        >
                                            {color}
                                        </span>
                                    ))}
                                </div>
                            </div>

                            {/* Avoid colors */}
                            <div>
                                <p className="text-gray-500 text-xs font-medium uppercase tracking-wider mb-2">
                                    ✕ Colors to Avoid
                                </p>
                                <div className="flex flex-wrap gap-2">
                                    {color_theory.avoid_colors.map((color, i) => (
                                        <span
                                            key={i}
                                            className="px-3 py-1 rounded-full bg-red-500/10 border border-red-500/30 text-red-400 text-xs font-medium"
                                        >
                                            {color}
                                        </span>
                                    ))}
                                </div>
                            </div>

                            {/* Undertone note */}
                            <p className="mt-3 text-gray-500 text-xs italic">
                                💡 {color_theory.undertone_note}
                            </p>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* ─── SECTION 3: Outfit Breakdown (Owned Items) ─── */}
            <motion.div
                initial={{ opacity: 0, y: 30 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.6 }}
                className="w-full mt-8"
            >
                <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
                    <span>👔</span> Your Outfit Breakdown
                </h3>

                <div className="space-y-3">
                    {wardrobe.items.map((item, i) => (
                        <motion.div
                            key={item.id}
                            initial={{ opacity: 0, x: -20 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ delay: 0.7 + i * 0.1 }}
                            className="flex items-center gap-4 px-4 py-3 rounded-xl bg-white/[0.03] border border-white/5 hover:bg-white/[0.06] transition-colors"
                        >
                            <span className="text-2xl">{SLOT_ICONS[item.slot] || "👗"}</span>
                            <div className="flex-1 min-w-0">
                                <p className="text-white text-sm font-medium truncate">
                                    {item.sub_category}
                                </p>
                                <p className="text-gray-500 text-xs">
                                    {item.color} • {item.pattern} • {item.style}
                                </p>
                            </div>

                            {/* Owned badge (green) */}
                            <span className="px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-medium whitespace-nowrap">
                                ✓ In Closet
                            </span>

                            {/* Confidence bar */}
                            <div className="w-12 h-1.5 rounded-full bg-white/10 overflow-hidden">
                                <div
                                    className="h-full bg-gradient-to-r from-green-500 to-emerald-500 rounded-full"
                                    style={{ width: `${item.confidence * 100}%` }}
                                />
                            </div>
                        </motion.div>
                    ))}
                </div>
            </motion.div>

            {/* ─── SECTION 4: Red Gap Items + Affiliate Upsell ("Switzerland") ─── */}
            {affiliate_upsells.length > 0 && (
                <motion.div
                    initial={{ opacity: 0, y: 30 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 1.0 }}
                    className="w-full mt-8"
                >
                    <h3 className="text-lg font-bold text-white mb-2 flex items-center gap-2">
                        <span>🛍️</span> Complete Your Look
                    </h3>
                    <p className="text-gray-500 text-sm mb-4">
                        These items were featured in your editorial but aren't in your closet yet.
                    </p>

                    <div className="space-y-4">
                        {affiliate_upsells.map((upsell, i) => (
                            <motion.div
                                key={i}
                                initial={{ opacity: 0, y: 20 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ delay: 1.1 + i * 0.15 }}
                                className="rounded-2xl overflow-hidden border-2 border-red-500/30 bg-gradient-to-br from-red-500/5 via-transparent to-transparent"
                            >
                                {/* RED HIGHLIGHT BAR — marks this as a "gap item" */}
                                <div className="px-4 py-2 bg-red-500/10 border-b border-red-500/20 flex items-center gap-2">
                                    <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
                                    <span className="text-red-400 text-xs font-semibold uppercase tracking-wider">
                                        Missing from your closet
                                    </span>
                                </div>

                                <div className="p-4">
                                    {/* Product details */}
                                    <div className="flex items-start gap-4 mb-4">
                                        {/* Product image placeholder */}
                                        <div className="w-20 h-20 rounded-xl bg-gradient-to-br from-gray-800 to-gray-900 border border-white/10 flex items-center justify-center flex-shrink-0">
                                            <span className="text-3xl">
                                                {SLOT_ICONS[upsell.gap_item?.description?.toLowerCase().includes("sneaker") ? "sneakers" : "sunglasses"] || "🛒"}
                                            </span>
                                        </div>

                                        <div className="flex-1 min-w-0">
                                            <p className="text-white font-semibold text-sm mb-0.5">
                                                {upsell.product_name}
                                            </p>
                                            <p className="text-gray-500 text-xs mb-2">{upsell.brand}</p>

                                            {/* Price */}
                                            <div className="flex items-center gap-2">
                                                <span className="text-white font-bold text-lg">
                                                    ₹{upsell.price.toLocaleString("en-IN")}
                                                </span>
                                                <span className="text-gray-500 text-sm line-through">
                                                    ₹{upsell.original_price.toLocaleString("en-IN")}
                                                </span>
                                                <span className="text-green-400 text-xs font-bold">
                                                    {upsell.discount_pct}% OFF
                                                </span>
                                            </div>
                                        </div>
                                    </div>

                                    {/* Completion message */}
                                    <div className="mb-4 px-3 py-2.5 rounded-xl bg-gradient-to-r from-amber-500/10 to-orange-500/10 border border-amber-500/20">
                                        <p className="text-amber-300 text-xs font-medium">
                                            ⚡ Your look is {outfit_completion_pct}% complete. Buy these{" "}
                                            {upsell.gap_item?.description || "items"} to hit 100%.
                                        </p>
                                    </div>

                                    {/* Bank offer */}
                                    <div className="mb-4 flex items-center gap-2 px-3 py-2 rounded-xl bg-blue-500/5 border border-blue-500/20">
                                        <span className="text-lg">🏦</span>
                                        <p className="text-blue-300 text-xs font-medium">
                                            {upsell.bank_offer}
                                        </p>
                                    </div>

                                    {/* Affiliate CTA button */}
                                    <a
                                        href={upsell.affiliate_url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="block w-full"
                                    >
                                        <motion.button
                                            whileHover={{ scale: 1.02 }}
                                            whileTap={{ scale: 0.98 }}
                                            className="w-full py-3.5 rounded-xl bg-gradient-to-r from-red-600 to-pink-600 text-white font-semibold text-sm shadow-lg shadow-red-500/20 hover:shadow-red-500/40 transition-all flex items-center justify-center gap-2"
                                        >
                                            <span>Shop on {upsell.platform}</span>
                                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                                <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" />
                                            </svg>
                                        </motion.button>
                                    </a>

                                    {/* Gap reason (expandable) */}
                                    <button
                                        onClick={() => setExpandedUpsell(expandedUpsell === i ? null : i)}
                                        className="mt-3 text-gray-600 text-xs hover:text-gray-400 transition-colors flex items-center gap-1"
                                    >
                                        <span>{expandedUpsell === i ? "▸" : "▹"}</span>
                                        Why this recommendation?
                                    </button>
                                    <AnimatePresence>
                                        {expandedUpsell === i && (
                                            <motion.p
                                                initial={{ opacity: 0, height: 0 }}
                                                animate={{ opacity: 1, height: "auto" }}
                                                exit={{ opacity: 0, height: 0 }}
                                                className="text-gray-500 text-xs mt-2 pl-4 border-l-2 border-white/10"
                                            >
                                                {upsell.gap_reason}
                                                <br />
                                                <span className="text-purple-400">{upsell.style_context}</span>
                                            </motion.p>
                                        )}
                                    </AnimatePresence>
                                </div>
                            </motion.div>
                        ))}
                    </div>
                </motion.div>
            )}

            {/* ─── SECTION 5: Gamification Teaser (calls to Step 5 modal) ─── */}
            <motion.div
                initial={{ opacity: 0, y: 30 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 1.4 }}
                className="w-full mt-8 mb-4"
            >
                {/* Mascot quest mini preview */}
                <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={onShowGamification}
                    className="w-full rounded-2xl bg-gradient-to-r from-yellow-500/5 via-orange-500/5 to-red-500/5 border border-yellow-500/20 p-5 text-left hover:border-yellow-400/30 transition-all"
                >
                    <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-3">
                            <span className="text-2xl">🎴</span>
                            <div>
                                <p className="text-white font-semibold text-sm">
                                    {gamification.mascot_quest.cards_collected}/{gamification.mascot_quest.cards_total} Mascot Cards
                                </p>
                                <p className="text-gray-500 text-xs">
                                    Checkout to unlock physical card
                                </p>
                            </div>
                        </div>
                        <svg className="w-5 h-5 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                        </svg>
                    </div>

                    {/* Mini progress bar */}
                    <div className="w-full h-1.5 rounded-full bg-white/10 overflow-hidden">
                        <div
                            className="h-full bg-gradient-to-r from-yellow-500 via-orange-500 to-red-500 rounded-full transition-all duration-1000"
                            style={{ width: `${(gamification.mascot_quest.cards_collected / gamification.mascot_quest.cards_total) * 100}%` }}
                        />
                    </div>
                </motion.button>

                {/* Style Graph mini preview */}
                <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={onShowGamification}
                    className="w-full mt-3 rounded-2xl bg-gradient-to-r from-emerald-500/5 via-teal-500/5 to-cyan-500/5 border border-emerald-500/20 p-5 text-left hover:border-emerald-400/30 transition-all"
                >
                    <div className="flex items-center gap-3">
                        <span className="text-2xl">📊</span>
                        <div className="flex-1">
                            <p className="text-white font-semibold text-sm">
                                {gamification.style_graph.reward_description}
                            </p>
                            <div className="mt-2 w-full h-1.5 rounded-full bg-white/10 overflow-hidden">
                                <div
                                    className="h-full bg-gradient-to-r from-emerald-500 to-teal-500 rounded-full transition-all duration-1000"
                                    style={{ width: `${gamification.style_graph.progress_pct}%` }}
                                />
                            </div>
                        </div>
                        <svg className="w-5 h-5 text-gray-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                        </svg>
                    </div>
                </motion.button>
            </motion.div>

            {/* ─── FOOTER: Share / Save ─── */}
            <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 1.6 }}
                className="w-full flex gap-3 mt-4 mb-8"
            >
                <button className="flex-1 py-3 rounded-xl bg-white/5 border border-white/10 text-gray-400 text-sm font-medium hover:bg-white/10 hover:text-white transition-all flex items-center justify-center gap-2">
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M7.217 10.907a2.25 2.25 0 100 2.186m0-2.186c.18.324.283.696.283 1.093s-.103.77-.283 1.093m0-2.186l9.566-5.314m-9.566 7.5l9.566 5.314m0 0a2.25 2.25 0 103.935 2.186 2.25 2.25 0 00-3.935-2.186zm0-12.814a2.25 2.25 0 103.933-2.185 2.25 2.25 0 00-3.933 2.185z" />
                    </svg>
                    Share
                </button>
                <button className="flex-1 py-3 rounded-xl bg-white/5 border border-white/10 text-gray-400 text-sm font-medium hover:bg-white/10 hover:text-white transition-all flex items-center justify-center gap-2">
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M17.593 3.322c1.1.128 1.907 1.077 1.907 2.185V21L12 17.25 4.5 21V5.507c0-1.108.806-2.057 1.907-2.185a48.507 48.507 0 0111.186 0z" />
                    </svg>
                    Save Look
                </button>
                <button className="flex-1 py-3 rounded-xl bg-gradient-to-r from-purple-600 to-pink-600 text-white text-sm font-semibold hover:shadow-[0_0_30px_rgba(147,51,234,0.3)] transition-all flex items-center justify-center gap-2">
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182M21.015 4.356v4.992" />
                    </svg>
                    Regenerate
                </button>
            </motion.div>
        </div>
    );
};

export default VibeCardResult;
