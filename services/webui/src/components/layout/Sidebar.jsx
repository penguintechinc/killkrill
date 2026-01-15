import React, { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  Menu,
  X,
  LayoutDashboard,
  Activity,
  Network,
  Server,
  Zap,
  Settings,
  ChevronDown,
  FileText,
  BarChart3,
  Radio,
} from "lucide-react";

const Sidebar = () => {
  const [isOpen, setIsOpen] = useState(true);
  const [expandedCategory, setExpandedCategory] = useState("Dashboard");
  const location = useLocation();

  const categories = [
    {
      name: "Dashboard",
      icon: LayoutDashboard,
      path: "/",
      items: [],
    },
    {
      name: "Monitoring",
      icon: Activity,
      items: [
        { name: "Sensors", path: "/sensors", icon: Radio },
        { name: "Logs", path: "/logs", icon: FileText },
        { name: "Metrics", path: "/metrics", icon: BarChart3 },
      ],
    },
    {
      name: "Fleet",
      icon: Network,
      path: "/fleet",
      items: [],
    },
    {
      name: "Infrastructure",
      icon: Server,
      path: "/infrastructure",
      items: [],
    },
    {
      name: "AI Analysis",
      icon: Zap,
      path: "/ai-analysis",
      items: [],
    },
    {
      name: "Settings",
      icon: Settings,
      path: "/settings",
      items: [],
    },
  ];

  const toggleCategory = (categoryName) => {
    setExpandedCategory(
      expandedCategory === categoryName ? null : categoryName,
    );
  };

  const isActive = (path) => {
    return location.pathname === path;
  };

  return (
    <div
      className={`h-screen bg-slate-900 text-slate-100 transition-all duration-300 ${isOpen ? "w-64" : "w-20"} flex flex-col border-r border-slate-700`}
    >
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-slate-700">
        {isOpen && (
          <h1 className="text-xl font-bold text-amber-500">Killkrill</h1>
        )}
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="p-2 hover:bg-slate-800 rounded-lg transition-colors"
        >
          {isOpen ? <X size={20} /> : <Menu size={20} />}
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-4 px-3">
        {categories.map((category) => {
          const IconComponent = category.icon;
          const isExpanded = expandedCategory === category.name;
          const hasItems = category.items && category.items.length > 0;
          const isCategoryActive = category.path && isActive(category.path);

          return (
            <div key={category.name} className="mb-2">
              {/* Category Button/Link */}
              {hasItems ? (
                <button
                  onClick={() => toggleCategory(category.name)}
                  className="w-full flex items-center justify-between p-3 rounded-lg hover:bg-slate-800 transition-colors group"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <IconComponent
                      size={20}
                      className="flex-shrink-0 text-amber-500 group-hover:text-amber-400"
                    />
                    {isOpen && (
                      <span className="text-sm font-medium truncate">
                        {category.name}
                      </span>
                    )}
                  </div>
                  {isOpen && (
                    <ChevronDown
                      size={16}
                      className={`flex-shrink-0 transition-transform ${
                        isExpanded ? "rotate-180" : ""
                      }`}
                    />
                  )}
                </button>
              ) : (
                <Link
                  to={category.path}
                  className={`w-full flex items-center justify-between p-3 rounded-lg hover:bg-slate-800 transition-colors group ${
                    isCategoryActive
                      ? "bg-slate-800 border-l-2 border-amber-500"
                      : ""
                  }`}
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <IconComponent
                      size={20}
                      className={`flex-shrink-0 ${
                        isCategoryActive
                          ? "text-amber-400"
                          : "text-amber-500 group-hover:text-amber-400"
                      }`}
                    />
                    {isOpen && (
                      <span
                        className={`text-sm font-medium truncate ${
                          isCategoryActive ? "text-amber-400" : ""
                        }`}
                      >
                        {category.name}
                      </span>
                    )}
                  </div>
                </Link>
              )}

              {/* Submenu Items */}
              {hasItems && isOpen && isExpanded && (
                <div className="ml-6 mt-1 space-y-1">
                  {category.items.map((item) => {
                    const ItemIcon = item.icon;
                    const isItemActive = isActive(item.path);

                    return (
                      <Link
                        key={item.name}
                        to={item.path}
                        className={`flex items-center gap-2 p-2 text-sm rounded hover:bg-slate-800 transition-colors ${
                          isItemActive
                            ? "text-amber-400 bg-slate-800 border-l-2 border-amber-500"
                            : "text-slate-300 hover:text-amber-400"
                        }`}
                      >
                        <ItemIcon size={16} />
                        {item.name}
                      </Link>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="border-t border-slate-700 p-3">
        {isOpen && (
          <div className="text-xs text-slate-400">
            <p className="font-semibold text-amber-500 mb-1">v1.0.0</p>
            <p>Ready for deployment</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default Sidebar;
