"""Suggested office workspaces. These descriptions confer no access or authority."""

def planned_sections(*items):
    return tuple({'icon':icon, 'title':title, 'description':description, 'status':'Planned'} for icon,title,description in items)


ADDITIONAL_PRESETS = {
    'budget': planned_sections(('fa-chart-pie','Annual budget preparation','Prepare office proposals, resource estimates and the annual budget.'), ('fa-layer-group','Appropriations and allotments','Review authorized funding and controlled allotment releases.'), ('fa-clipboard-check','Obligation control','Follow requests, certifications and obligation balances.')),
    'treasury': planned_sections(('fa-receipt','Collections and deposits','Record receipts, deposit allocations and bank evidence.'), ('fa-money-check-alt','Payment and release queue','Follow reviewed checks, bank advice and actual payment releases.'), ('fa-university','Cash and bank reconciliation','Review bank balances, reconciling items and daily cash positions.')),
    'mpdo': planned_sections(('fa-map-marked-alt','Development plans','Organize local development plans, priorities and investment programs.'), ('fa-project-diagram','Project monitoring','Follow approved projects, milestones and accomplishment reports.'), ('fa-chart-bar','Local data and statistics','Maintain planning indicators and reference information.')),
    'meo': planned_sections(('fa-hard-hat','Infrastructure projects','Follow public works, project schedules and field progress.'), ('fa-drafting-compass','Plans and inspections','Organize technical plans, inspection requests and findings.'), ('fa-road','Facilities and maintenance','Track infrastructure condition and maintenance priorities.')),
    'mho': planned_sections(('fa-heartbeat','Health services','Coordinate clinic services and public health activities.'), ('fa-notes-medical','Program monitoring','Organize health program schedules and accomplishment summaries.'), ('fa-medkit','Health supplies','Plan supplies and equipment needs for municipal health services.')),
    'mao': planned_sections(('fa-seedling','Agricultural services','Coordinate farmer support, field visits and extension services.'), ('fa-tractor','Production and assistance programs','Plan agricultural inputs, equipment support and distributions.'), ('fa-leaf','Field monitoring','Organize crop, livestock and fisheries monitoring.')),
    'mcr': planned_sections(('fa-file-signature','Civil registration','Organize birth, marriage and death registration work.'), ('fa-copy','Certificates and requests','Follow certificate requests and authorized release steps.'), ('fa-archive','Registry records','Organize registry references and reporting duties.')),
    'assessor': planned_sections(('fa-home','Property assessment','Organize property declarations and assessment work.'), ('fa-map','Property mapping','Maintain mapping references and field verification work.'), ('fa-file-alt','Assessment requests','Follow certifications, reassessments and property inquiries.')),
    'bplo': planned_sections(('fa-store','Business permits','Follow applications, renewals and permit processing.'), ('fa-clipboard-check','Requirements and inspections','Coordinate document checks and office endorsements.'), ('fa-chart-line','Business activity reports','Organize permit activity and service summaries.')),
    'mdrrmo': planned_sections(('fa-life-ring','Preparedness and response','Coordinate readiness activities and response priorities.'), ('fa-exclamation-triangle','Incident monitoring','Organize incident reports and situation updates.'), ('fa-box-open','Resources and relief','Track response resources and relief coordination.')),
    'menro': planned_sections(('fa-recycle','Waste management','Coordinate collection, segregation and environmental programs.'), ('fa-tree','Environmental services','Organize environmental requests, inspections and field activities.'), ('fa-water','Compliance and monitoring','Follow monitoring schedules and environmental reports.')),
    'mayors-office': planned_sections(('fa-inbox','Executive correspondence','Organize incoming correspondence and office endorsements.'), ('fa-calendar-alt','Appointments and coordination','Coordinate official schedules and inter-office meetings.'), ('fa-tasks','Executive priorities','Follow municipal priorities and office commitments.')),
    'sb': planned_sections(('fa-landmark','Legislative agenda','Organize session agendas, committee work and referrals.'), ('fa-gavel','Ordinances and resolutions','Follow measures, deliberations and adopted records.'), ('fa-file-signature','Official communications','Organize legislative correspondence and requests.')),
    'peso': planned_sections(('fa-briefcase','Employment services','Coordinate job matching, employer contacts and employment assistance.'), ('fa-users','Training and job fairs','Plan skills activities, orientations and employment events.'), ('fa-chart-bar','Service monitoring','Organize employment program accomplishment reports.')),
    'tourism': planned_sections(('fa-compass','Tourism services','Organize visitor information and tourism coordination.'), ('fa-calendar-day','Culture and events','Coordinate cultural activities and local events.'), ('fa-camera','Destinations and promotion','Maintain approved destination information and promotion plans.')),
    'ict': planned_sections(('fa-desktop','Technical support','Organize user support requests and equipment concerns.'), ('fa-network-wired','Systems and infrastructure','Coordinate approved system maintenance and connectivity work.'), ('fa-shield-alt','Access and continuity','Follow account support, continuity and security review duties.')),
}

PRESET_ALIASES = {
    'accounting':'acctg', 'municipal-accounting-office':'acctg',
    'human-resources':'hr', 'hrmo':'hr', 'human-resource-management-office':'hr',
    'general-services-office':'gso', 'municipal-budget-office':'budget', 'mbo':'budget',
    'treasurer':'treasury', 'mto':'treasury', 'municipal-treasurers-office':'treasury',
    'planning':'mpdo', 'municipal-planning-and-development-office':'mpdo',
    'engineering':'meo', 'municipal-engineering-office':'meo',
    'health':'mho', 'rhu':'mho', 'municipal-health-office':'mho',
    'agriculture':'mao', 'municipal-agriculture-office':'mao',
    'civil-registry':'mcr', 'municipal-civil-registrar':'mcr',
    'municipal-assessors-office':'assessor', 'business-permits':'bplo',
    'drrmo':'mdrrmo', 'environment':'menro', 'mayor':'mayors-office', 'office-of-the-mayor':'mayors-office',
    'sangguniang-bayan':'sb', 'mis':'ict', 'it':'ict',
}
