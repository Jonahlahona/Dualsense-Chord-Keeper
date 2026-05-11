import React, { useState, useEffect } from 'react';
import {
    Monitor, Smartphone, Laptop, Tablet, Tv,
    Gamepad2, Bell, X, Plus, Trash2, Play
} from 'lucide-react';

// --- Helper Components for Controller Glyphs ---

const PSGlyph = ({ type }) => {
    const baseClasses = "w-7 h-7 flex items-center justify-center rounded-full border border-slate-700 bg-slate-800 shadow-inner shrink-0";

    switch (type) {
        case 'Triangle':
            return (
                <div className={baseClasses} title="Triangle">
                    <svg viewBox="0 0 24 24" fill="none" stroke="#22c55e" strokeWidth="2.5" className="w-4 h-4">
                        <polygon points="12,4 20,18 4,18" strokeLinejoin="round" />
                    </svg>
                </div>
            );
        case 'Circle':
            return (
                <div className={baseClasses} title="Circle">
                    <svg viewBox="0 0 24 24" fill="none" stroke="#ef4444" strokeWidth="2.5" className="w-4 h-4">
                        <circle cx="12" cy="12" r="8" />
                    </svg>
                </div>
            );
        case 'Cross':
            return (
                <div className={baseClasses} title="Cross">
                    <svg viewBox="0 0 24 24" fill="none" stroke="#3b82f6" strokeWidth="2.5" className="w-4 h-4">
                        <path d="M7 7l10 10M17 7L7 17" strokeLinecap="round" />
                    </svg>
                </div>
            );
        case 'Square':
            return (
                <div className={baseClasses} title="Square">
                    <svg viewBox="0 0 24 24" fill="none" stroke="#ec4899" strokeWidth="2.5" className="w-4 h-4">
                        <rect x="6" y="6" width="12" height="12" rx="2" strokeLinejoin="round" />
                    </svg>
                </div>
            );
        case 'PS':
            return (
                <div className="w-8 h-7 flex items-center justify-center rounded-[10px] bg-slate-950 border border-slate-700 shadow-sm shrink-0" title="PS Button">
                    <span className="text-white text-[11px] font-black tracking-tighter">PS</span>
                </div>
            );
        case 'Create':
            return (
                <div className="w-4 h-6 flex items-center justify-center rounded-sm bg-slate-800 border border-slate-600 shrink-0" title="Create Button">
                    <div className="w-0.5 h-3 border-l border-t border-slate-400"></div>
                </div>
            );
        case 'Options':
            return (
                <div className="w-4 h-6 flex items-center justify-center rounded-sm bg-slate-800 border border-slate-600 shrink-0" title="Options Button">
                    <div className="flex gap-[2px]">
                        <div className="w-[2px] h-[2px] bg-slate-400"></div>
                        <div className="w-[2px] h-[2px] bg-slate-400"></div>
                        <div className="w-[2px] h-[2px] bg-slate-400"></div>
                    </div>
                </div>
            );
        case 'Mute':
            return (
                <div className="w-6 h-3 flex items-center justify-center rounded-sm bg-slate-800 border border-slate-600 shadow-inner shrink-0" title="Mute Button">
                    <div className="w-3 h-0.5 bg-orange-400/80 rounded-full"></div>
                </div>
            );
        case 'L1':
        case 'R1':
        case 'L2':
        case 'R2':
            return (
                <div className="px-2 h-7 flex items-center justify-center rounded bg-slate-800 border border-slate-700 text-[10px] text-slate-300 font-bold shrink-0" title={type}>
                    {type}
                </div>
            );
        default:
            return null;
    }
};

const getIcon = (name, className = "") => {
    const props = { size: 18, className };
    switch (name) {
        case 'Monitor': return <Monitor {...props} />;
        case 'Smartphone': return <Smartphone {...props} />;
        case 'Laptop': return <Laptop {...props} />;
        case 'Tablet': return <Tablet {...props} />;
        case 'Tv': return <Tv {...props} />;
        default: return <Monitor {...props} />;
    }
};

// --- Notification Overlay Component ---

const NotificationPopup = ({ profiles, isVisible, onClose }) => {
    return (
        <div className={`fixed bottom-6 right-6 z-50 transition-all duration-500 ease-out transform ${isVisible ? 'translate-y-0 opacity-100' : 'translate-y-8 opacity-0 pointer-events-none'
            }`}>
            <div className="w-[22rem] sm:w-[26rem] bg-slate-900/85 backdrop-blur-xl border border-slate-700/50 rounded-2xl shadow-2xl shadow-blue-900/20 overflow-hidden flex flex-col">
                {/* Header */}
                <div className="bg-slate-800/60 px-4 py-3 border-b border-slate-700/50 flex justify-between items-center">
                    <div className="flex items-center gap-2 text-blue-400">
                        <Gamepad2 size={18} />
                        <span className="font-semibold text-sm tracking-wide text-slate-200">DualSense Device Profiles</span>
                    </div>
                    <button onClick={onClose} className="text-slate-400 hover:text-white transition-colors">
                        <X size={16} />
                    </button>
                </div>

                {/* Body */}
                <div className="p-2 space-y-1">
                    {profiles.length === 0 ? (
                        <div className="p-4 text-center text-slate-400 text-sm">No profiles configured.</div>
                    ) : (
                        profiles.map((profile) => (
                            <div key={profile.id} className="flex items-center justify-between p-3 rounded-xl hover:bg-slate-800/50 transition-colors group">
                                {/* Chord (Buttons) */}
                                <div className="flex items-center gap-2">
                                    <PSGlyph type="PS" />
                                    <span className="text-slate-500 text-xs font-bold">+</span>
                                    <PSGlyph type={profile.button2} />
                                </div>

                                {/* Separator Line */}
                                <div className="h-px bg-slate-700/50 flex-1 mx-4 group-hover:bg-slate-600 transition-colors"></div>

                                {/* Device Info */}
                                <div className="flex items-center gap-2.5 text-slate-200 min-w-[100px] justify-end">
                                    <span className="text-sm font-medium truncate max-w-[100px]">{profile.deviceName}</span>
                                    <div className="text-slate-400 flex-shrink-0">
                                        {getIcon(profile.iconType)}
                                    </div>
                                </div>
                            </div>
                        ))
                    )}
                </div>

                {/* Bottom edge accent */}
                <div className="h-1 w-full bg-gradient-to-r from-blue-600 via-indigo-500 to-purple-600"></div>
            </div>
        </div>
    );
};

// --- Main Application ---

export default function App() {
    const [showNotification, setShowNotification] = useState(false);
    const [triggerButton, setTriggerButton] = useState('Mute');
    const [profiles, setProfiles] = useState([]);

    const buttonOptions = ['Triangle', 'Circle', 'Cross', 'Square'];
    const triggerBtnOptions = ['Mute', 'PS', 'Create', 'Options', 'Triangle', 'Circle', 'Cross', 'Square', 'L1', 'R1', 'L2', 'R2', 'Touchpad'];
    const iconOptions = ['Monitor', 'Smartphone', 'Laptop', 'Tablet', 'Tv'];

    // Load config on mount
    useEffect(() => {
        const load = async () => {
            if (window.pywebview && window.pywebview.api) {
                const data = await window.pywebview.api.load_config();
                if (data) {
                    try {
                        const parsed = JSON.parse(data);
                        if (parsed.profiles) {
                            setProfiles(parsed.profiles);
                            if (parsed.triggerButton) setTriggerButton(parsed.triggerButton);
                        } else if (Array.isArray(parsed)) {
                            setProfiles(parsed); // Legacy format fallback
                        }
                    } catch (e) {
                        console.error("Failed to parse config", e);
                    }
                }
            }
        };
        window.addEventListener('pywebviewready', load);
        load();
        return () => window.removeEventListener('pywebviewready', load);
    }, []);

    const saveConfig = (newProfiles, newButton) => {
        if (window.pywebview && window.pywebview.api) {
            window.pywebview.api.save_config(JSON.stringify({
                triggerButton: newButton,
                profiles: newProfiles
            }));
        }
    };

    // Auto-hide notification after 8 seconds
    useEffect(() => {
        let timer;
        if (showNotification) {
            timer = setTimeout(() => setShowNotification(false), 8000);
        }
        return () => clearTimeout(timer);
    }, [showNotification]);

    const triggerNotification = () => {
        if (window.pywebview && window.pywebview.api) {
            // Trigger global overlay through Python
            window.pywebview.api.show_notification(JSON.stringify(profiles));
        } else {
            // Fallback: local notification
            setShowNotification(false);
            setTimeout(() => setShowNotification(true), 50);
        }
    };

    const updateProfile = (id, field, value) => {
        const newProfiles = profiles.map(p => p.id === id ? { ...p, [field]: value } : p);
        setProfiles(newProfiles);
        saveConfig(newProfiles, triggerButton);
    };

    const addProfile = () => {
        const newId = profiles.length > 0 ? Math.max(...profiles.map(p => p.id)) + 1 : 1;
        const newProfiles = [...profiles, { id: newId, button1: 'PS', button2: 'Cross', deviceName: 'New Device', iconType: 'Tablet' }];
        setProfiles(newProfiles);
        saveConfig(newProfiles, triggerButton);
    };

    const removeProfile = (id) => {
        const newProfiles = profiles.filter(p => p.id !== id);
        setProfiles(newProfiles);
        saveConfig(newProfiles, triggerButton);
    };

    const updateTriggerButton = (value) => {
        setTriggerButton(value);
        saveConfig(profiles, value);
    };

    return (
        <div className="min-h-screen bg-slate-950 text-slate-300 font-sans relative overflow-hidden">
            {/* Background ambient glow */}
            <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full max-w-3xl h-96 bg-blue-900/20 blur-[120px] rounded-full pointer-events-none"></div>

            <div className="max-w-4xl mx-auto p-6 relative z-10">

                {/* Header Section */}
                <header className="flex flex-col md:flex-row justify-between items-start md:items-center py-8 mb-8 border-b border-slate-800">
                    <div>
                        <h1 className="text-3xl font-bold text-white flex items-center gap-3">
                            <Gamepad2 className="text-blue-500" size={32} />
                            DualSense Link
                        </h1>
                        <p className="text-slate-400 mt-2">Manage and test your controller's Bluetooth switching shortcuts.</p>
                    </div>

                    <button
                        onClick={triggerNotification}
                        className="mt-6 md:mt-0 flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white px-5 py-2.5 rounded-lg font-medium transition-all shadow-lg shadow-blue-600/20 active:scale-95"
                    >
                        <Bell size={18} />
                        Show Reminder
                    </button>
                </header>

                {/* Configuration Section */}
                <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-6 shadow-xl backdrop-blur-sm mb-6">
                    <h2 className="text-xl font-semibold text-slate-100 mb-4">Activation Shortcut</h2>
                    <p className="text-sm text-slate-400 mb-6">Choose the button on your DualSense controller that will activate the overlay notification.</p>
                    
                    <div className="flex flex-col sm:flex-row items-center gap-4 bg-slate-800/40 p-4 rounded-xl border border-slate-700/50">
                        <div className="flex items-center gap-3">
                            <PSGlyph type={triggerButton} />
                            <select
                                value={triggerButton}
                                onChange={(e) => updateTriggerButton(e.target.value)}
                                className="bg-slate-900 border border-slate-700 text-slate-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:border-blue-500 w-32"
                            >
                                {triggerBtnOptions.map(opt => <option key={opt} value={opt}>{opt}</option>)}
                            </select>
                        </div>
                    </div>
                </div>

                <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-6 shadow-xl backdrop-blur-sm">
                    <div className="flex justify-between items-center mb-6">
                        <h2 className="text-xl font-semibold text-slate-100">Chord Configurations</h2>
                        <button
                            onClick={addProfile}
                            className="flex items-center gap-1.5 text-sm text-blue-400 hover:text-blue-300 transition-colors bg-blue-400/10 hover:bg-blue-400/20 px-3 py-1.5 rounded-md"
                        >
                            <Plus size={16} /> Add Device
                        </button>
                    </div>

                    <div className="space-y-4">
                        {profiles.length === 0 && (
                            <div className="text-center py-10 border-2 border-dashed border-slate-800 rounded-xl text-slate-500">
                                No configurations setup. Add a device to get started.
                            </div>
                        )}

                        {profiles.map((profile) => (
                            <div key={profile.id} className="flex flex-col lg:flex-row lg:items-center gap-4 bg-slate-800/40 p-4 rounded-xl border border-slate-700/50">

                                {/* Button Selection */}
                                <div className="flex items-center gap-3 flex-1">
                                    <div className="flex items-center gap-2">
                                        <PSGlyph type="PS" />
                                        <span className="text-slate-500 font-bold">+</span>
                                        <div className="flex items-center gap-2">
                                            <PSGlyph type={profile.button2} />
                                            <select
                                                value={profile.button2}
                                                onChange={(e) => updateProfile(profile.id, 'button2', e.target.value)}
                                                className="bg-slate-900 border border-slate-700 text-slate-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:border-blue-500 w-32"
                                            >
                                                {buttonOptions.map(opt => <option key={opt} value={opt}>{opt}</option>)}
                                            </select>
                                        </div>
                                    </div>
                                </div>

                                {/* Device Details */}
                                <div className="flex items-center gap-3 flex-1 mt-4 lg:mt-0 pt-4 lg:pt-0 border-t lg:border-t-0 border-slate-700/50 lg:border-l lg:pl-6">
                                    <input
                                        type="text"
                                        value={profile.deviceName}
                                        onChange={(e) => updateProfile(profile.id, 'deviceName', e.target.value)}
                                        placeholder="Device Name"
                                        className="flex-1 bg-slate-900 border border-slate-700 text-slate-200 rounded-md px-3 py-2 text-sm focus:outline-none focus:border-blue-500 placeholder-slate-600"
                                    />

                                    <div className="relative">
                                        <select
                                            value={profile.iconType}
                                            onChange={(e) => updateProfile(profile.id, 'iconType', e.target.value)}
                                            className="appearance-none bg-slate-900 border border-slate-700 text-transparent w-12 h-9 rounded-md focus:outline-none focus:border-blue-500 z-10 relative cursor-pointer"
                                        >
                                            {iconOptions.map(opt => <option key={opt} value={opt} className="text-slate-200 bg-slate-900">{opt}</option>)}
                                        </select>
                                        <div className="absolute inset-0 flex items-center justify-center text-slate-400 pointer-events-none z-0">
                                            {getIcon(profile.iconType)}
                                        </div>
                                    </div>

                                    <button
                                        onClick={() => removeProfile(profile.id)}
                                        className="p-2 text-slate-500 hover:text-red-400 hover:bg-red-400/10 rounded-md transition-colors ml-2"
                                        title="Remove Profile"
                                    >
                                        <Trash2 size={18} />
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Helper Note */}
                <div className="mt-6 flex items-start gap-3 bg-blue-900/10 border border-blue-900/30 p-4 rounded-xl">
                    <Play className="text-blue-400 mt-0.5 shrink-0" size={16} />
                    <p className="text-sm text-slate-400 leading-relaxed">
                        Click <strong>Show Reminder</strong> to test the notification overlay. In a standalone setup, this overlay would be triggered via a global hotkey or a background listener to remind you of your configured device mappings instantly.
                    </p>
                </div>
            </div>

            {/* Local Notification Portal */}
            <NotificationPopup
                profiles={profiles}
                isVisible={showNotification}
                onClose={() => setShowNotification(false)}
            />
        </div>
    );
}

// --- Global Notification View for Overlay Window ---
export function NotificationView() {
    const [profiles, setProfiles] = useState([]);
    const [isVisible, setIsVisible] = useState(false);

    useEffect(() => {
        // Expose function for Python to call
        window.triggerGlobalNotification = (profilesData) => {
            if (typeof profilesData === 'string') {
                profilesData = JSON.parse(profilesData);
            }
            setProfiles(profilesData);
            setIsVisible(false);
            setTimeout(() => setIsVisible(true), 50);
            
            // Auto-hide after 8 seconds
            setTimeout(() => setIsVisible(false), 8000);
        };
    }, []);

    return (
        <div className="w-screen h-screen overflow-hidden pointer-events-none">
            <NotificationPopup 
                profiles={profiles} 
                isVisible={isVisible} 
                onClose={() => setIsVisible(false)} 
            />
        </div>
    );
}