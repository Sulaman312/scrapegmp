function renderHours(hours) {
  document.getElementById('hoursTable').innerHTML = DAYS.map((day, i) => {
    const v = hours[day] || hours[day[0].toUpperCase() + day.slice(1)] || '';
    return `<div class="flex items-center gap-3">
      <span class="text-xs text-slate-500 w-24 shrink-0">${DAY_LBL[i]}</span>
      <input type="text" data-hours="${day}" class="fi" value="${esc(v)}" placeholder="9 AM – 5 PM  or  Closed"/>
    </div>`;
  }).join('');
}
