"use client";

export default function NiprixLoader() {
  return (
    <main className="niprix-loader">
      <div className="niprix-loader-content">
        {Array.from({ length: 16 }).map((_, index) => (
          <div className="niprix-cuboid" key={index}>
            <div className="niprix-side" />
            <div className="niprix-side" />
            <div className="niprix-side" />
            <div className="niprix-side" />
            <div className="niprix-side" />
            <div className="niprix-side" />
          </div>
        ))}
      </div>

      <div className="niprix-loader-brand">
        <div className="niprix-brand-name">
          <span className="niprix-blue">NIP</span>
          <span className="niprix-dark">RI</span>
          <span className="niprix-orange">X</span>
        </div>

        <div className="niprix-brand-line">
          <span />
          <strong>CONNECT TO EVERYONE</strong>
          <span />
        </div>

        <div className="niprix-brand-subtitle">
          ENTERPRISE REAL ESTATE CRM
        </div>
      </div>
    </main>
  );
}