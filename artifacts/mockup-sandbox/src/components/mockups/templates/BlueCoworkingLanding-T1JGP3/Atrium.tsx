import './fonts.css';
import asset0 from "./assets/lp-26-hero.png";

import React from "react";

export default function Atrium() {
  return (
    <div className="w-full h-full overflow-hidden bg-[#0A2FFF] text-white font-['Outfit'] relative flex flex-col items-center">
      {/* Navbar */}
      <nav className="w-full flex items-center justify-between px-16 py-8 relative z-20">
        <div className="text-2xl font-bold tracking-tight flex items-center gap-2">
          <div className="w-6 h-6 rounded-full bg-white flex items-center justify-center">
            <div className="w-2 h-2 rounded-full bg-[#0A2FFF]"></div>
          </div>
          Atrium Collective
        </div>
        <div className="flex items-center gap-10 font-medium text-lg opacity-90">
          <a href="#" className="hover:opacity-100 transition-opacity">Spaces</a>
          <a href="#" className="hover:opacity-100 transition-opacity">Pricing</a>
          <a href="#" className="hover:opacity-100 transition-opacity">Members</a>
          <a href="#" className="hover:opacity-100 transition-opacity">Contact</a>
        </div>
        <button className="bg-white text-[#0A2FFF] px-8 py-3 rounded-full font-bold text-lg hover:bg-opacity-90 transition-colors shadow-xl shadow-black/10">
          Book a tour
        </button>
      </nav>

      {/* Main Content */}
      <main className="flex-1 w-full px-16 flex items-center relative z-10">
        
        {/* Left Column - Text */}
        <div className="w-[60%] z-20 pt-10">
          <h1 className="text-[5.5rem] font-bold leading-[1.05] mb-8 tracking-tight">
            Workspaces that <br />
            <span className="relative inline-block whitespace-nowrap">
              actually
              {/* Hand-drawn marker ellipse */}
              <svg 
                className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[120%] h-[150%] pointer-events-none text-white/90" 
                viewBox="0 0 200 100" 
                fill="none" 
                xmlns="http://www.w3.org/2000/svg"
                preserveAspectRatio="none"
              >
                <path 
                  d="M100 10C40 10 10 30 10 50C10 70 40 90 100 90C160 90 190 70 190 50C190 30 160 10 100 10Z" 
                  stroke="currentColor" 
                  strokeWidth="4" 
                  strokeLinecap="round" 
                  strokeLinejoin="round" 
                  className="opacity-90"
                  style={{
                    strokeDasharray: "600",
                    strokeDashoffset: "0",
                    filter: "url(#displacementFilter)"
                  }}
                />
                <defs>
                  <filter id="displacementFilter">
                    <feTurbulence type="fractalNoise" baseFrequency="0.05" numOctaves="2" result="noise" />
                    <feDisplacementMap in="SourceGraphic" in2="noise" scale="3" xChannelSelector="R" yChannelSelector="G" />
                  </filter>
                </defs>
              </svg>
            </span>
            {" "} work.
          </h1>
          
          <p className="text-2xl opacity-90 leading-relaxed mb-14 max-w-[500px] font-light">
            Flexible desks, private studios, and sunlit meeting rooms designed for focus and collaboration. Step into your best workday.
          </p>

          {/* Stats Row */}
          <div className="flex gap-16 items-center">
            <div className="flex flex-col gap-1">
              <span className="text-5xl font-extrabold tracking-tight">24/7</span>
              <span className="text-sm uppercase tracking-[0.2em] opacity-80 font-semibold">Access</span>
            </div>
            <div className="flex flex-col gap-1">
              <span className="text-5xl font-extrabold tracking-tight">3</span>
              <span className="text-sm uppercase tracking-[0.2em] opacity-80 font-semibold">Locations</span>
            </div>
            <div className="flex flex-col gap-1">
              <span className="text-5xl font-extrabold tracking-tight">1G</span>
              <span className="text-sm uppercase tracking-[0.2em] opacity-80 font-semibold">Fiber WiFi</span>
            </div>
          </div>
        </div>

        {/* Right Column - Image Bleed */}
        <div className="absolute right-0 top-0 h-full w-[45%] z-0 flex items-center justify-end">
          <div className="relative w-full h-[85%] bg-black rounded-l-[60px] overflow-hidden shadow-2xl translate-x-10">
            <img 
              src={asset0} 
              alt="Coworking space interior" 
              className="w-full h-full object-cover opacity-80 mix-blend-screen scale-105"
            />
            {/* Duotone effect overlay */}
            <div className="absolute inset-0 bg-[#0A2FFF] mix-blend-overlay opacity-30"></div>
            <div className="absolute inset-0 border-[1px] border-white/20 rounded-l-[60px]"></div>
          </div>
        </div>

      </main>

      {/* Decorative Grid Lines Background */}
      <div className="absolute inset-0 pointer-events-none opacity-[0.03] mix-blend-overlay z-0" 
           style={{ backgroundImage: 'linear-gradient(white 1px, transparent 1px), linear-gradient(90deg, white 1px, transparent 1px)', backgroundSize: '40px 40px' }}>
      </div>
    </div>
  );
}
