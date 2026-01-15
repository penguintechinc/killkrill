import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import {
  Search,
  Bell,
  User,
  Settings,
  LogOut,
  ChevronDown,
} from "lucide-react";

const Header = () => {
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [notifications, setNotifications] = useState(3);
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  const handleProfileClick = () => {
    setShowUserMenu(false);
    navigate("/settings");
  };

  return (
    <header className="bg-slate-900 border-b border-amber-900/30 px-8 py-4 flex items-center justify-between">
      {/* Logo/Brand */}
      <div className="flex items-center gap-4">
        <button
          onClick={() => navigate("/")}
          className="flex items-center hover:opacity-80 transition-opacity"
        >
          <img
            src="/logo.png"
            alt="KillKrill"
            className="h-10 w-auto"
          />
        </button>
      </div>

      {/* Search Bar */}
      <div className="flex-1 max-w-md mx-8">
        <div className="relative">
          <Search
            className="absolute left-3 top-1/2 transform -translate-y-1/2 text-amber-500/60"
            size={18}
          />
          <input
            type="text"
            placeholder="Search..."
            className="w-full pl-10 pr-4 py-2 bg-slate-800 border border-amber-900/30 rounded-lg text-slate-100 placeholder-slate-500 focus:outline-none focus:border-amber-500/50 focus:ring-1 focus:ring-amber-500/30 transition-all"
          />
        </div>
      </div>

      {/* Right Section */}
      <div className="flex items-center gap-6">
        {/* Notifications */}
        <button className="relative p-2 hover:bg-slate-800 rounded-lg transition-colors group">
          <Bell
            size={20}
            className="text-amber-500 group-hover:text-amber-400"
          />
          {notifications > 0 && (
            <span className="absolute top-1 right-1 bg-red-500 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center font-semibold">
              {notifications}
            </span>
          )}
        </button>

        {/* User Menu */}
        <div className="relative">
          <button
            onClick={() => setShowUserMenu(!showUserMenu)}
            className="flex items-center gap-2 p-2 hover:bg-slate-800 rounded-lg transition-colors group"
          >
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 bg-gradient-to-br from-amber-500 to-amber-600 rounded-full flex items-center justify-center">
                <User size={16} className="text-slate-900" />
              </div>
              <span className="text-sm font-medium text-amber-500 group-hover:text-amber-400">
                {user?.username || "Admin"}
              </span>
            </div>
            <ChevronDown
              size={16}
              className={`text-amber-500 group-hover:text-amber-400 transition-transform ${
                showUserMenu ? "rotate-180" : ""
              }`}
            />
          </button>

          {/* Dropdown Menu */}
          {showUserMenu && (
            <div className="absolute right-0 mt-2 w-48 bg-slate-800 border border-amber-900/30 rounded-lg shadow-lg overflow-hidden z-10">
              <div className="px-4 py-3 border-b border-amber-900/20">
                <p className="text-sm font-medium text-amber-500">
                  {user?.username || "Admin User"}
                </p>
                <p className="text-xs text-slate-400">
                  {user?.email || "admin@killkrill.local"}
                </p>
              </div>

              <div className="py-2">
                <button
                  onClick={handleProfileClick}
                  className="w-full flex items-center gap-3 px-4 py-2 text-sm text-slate-100 hover:bg-slate-700 hover:text-amber-400 transition-colors"
                >
                  <User size={16} />
                  Profile
                </button>
                <button
                  onClick={handleProfileClick}
                  className="w-full flex items-center gap-3 px-4 py-2 text-sm text-slate-100 hover:bg-slate-700 hover:text-amber-400 transition-colors"
                >
                  <Settings size={16} />
                  Settings
                </button>
              </div>

              <div className="border-t border-amber-900/20 py-2">
                <button
                  onClick={handleLogout}
                  className="w-full flex items-center gap-3 px-4 py-2 text-sm text-red-400 hover:bg-slate-700 transition-colors"
                >
                  <LogOut size={16} />
                  Logout
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};

export default Header;
