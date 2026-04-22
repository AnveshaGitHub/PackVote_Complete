# ai_itinerary.py — place in backend/ folder
# Uses Groq API (free — sign up at console.groq.com, no card needed)
# Dynamic destination research via Groq AI
# Fallback to minimal rule-based only when Groq fails

import os
import json
import requests
from datetime import datetime, timedelta

GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
GROQ_URL     = os.environ.get('GROQ_URL', '')

# ── 500+ Indian destinations (kept for autocomplete/validation) ──────────

INDIA_DESTINATIONS = {
    'Andhra Pradesh':    ['Visakhapatnam','Vijayawada','Tirupati','Araku Valley','Lepakshi','Nagarjunasagar','Srikalahasti','Horsley Hills'],
    'Arunachal Pradesh': ['Tawang','Ziro','Dirang','Bomdila','Namdapha','Pasighat','Mechuka','Along'],
    'Assam':             ['Kaziranga','Majuli','Guwahati','Jorhat','Tezpur','Haflong','Manas','Sibsagar','Sualkuchi'],
    'Bihar':             ['Bodh Gaya','Rajgir','Nalanda','Vaishali','Patna','Pawapuri','Vikramshila','Madhubani'],
    'Chhattisgarh':      ['Chitrakote','Jagdalpur','Raipur','Sirpur','Barnawapara','Tirathgarh','Bastar','Mainpat'],
    'Goa':               ['North Goa','South Goa','Panjim','Calangute','Anjuna','Palolem','Dudhsagar','Arambol','Vagator'],
    'Gujarat':           ['Rann of Kutch','Gir Forest','Ahmedabad','Vadodara','Surat','Dwarka','Somnath','Saputara','Champaner','Mandvi','Palitana','Lothal'],
    'Haryana':           ['Kurukshetra','Sultanpur','Morni Hills','Pinjore','Faridabad'],
    'Himachal Pradesh':  ['Manali','Shimla','Dharamsala','McLeod Ganj','Spiti Valley','Kaza','Kasol','Bir Billing','Dalhousie','Chail','Kinnaur','Khajjiar','Kullu','Sangla','Chitkul','Kalpa'],
    'Jharkhand':         ['Ranchi','Jamshedpur','Betla','Hundru Falls','Deoghar','Netarhat','Palamu'],
    'Karnataka':         ['Coorg','Mysuru','Hampi','Badami','Chikmagalur','Kabini','Dandeli','Gokarna','Mangalore','Udupi','Sakleshpur','Bidar','Shravanabelagola','Belur','Halebidu','Jog Falls','Agumbe'],
    'Kerala':            ['Munnar','Alleppey','Thekkady','Kovalam','Wayanad','Kochi','Thrissur','Varkala','Bekal','Athirappilly','Kumarakom','Marari','Kasaragod'],
    'Ladakh':            ['Leh','Nubra Valley','Pangong Lake','Zanskar','Turtuk','Hanle','Magnetic Hill','Diskit','Kargil','Hemis'],
    'Madhya Pradesh':    ['Khajuraho','Bandhavgarh','Kanha','Pench','Sanchi','Orchha','Gwalior','Pachmarhi','Mandu','Bhopal','Jabalpur','Amarkantak','Bhimbetka','Chanderi','Shivpuri'],
    'Maharashtra':       ['Mumbai','Pune','Aurangabad','Lonavala','Mahabaleshwar','Nashik','Kolhapur','Alibag','Matheran','Ajanta Ellora','Tadoba','Panchgani','Igatpuri','Malshej Ghat','Satara'],
    'Manipur':           ['Imphal','Loktak Lake','Keibul Lamjao','Moreh','Ukhrul','Dzuko Valley Manipur'],
    'Meghalaya':         ['Shillong','Cherrapunji','Mawlynnong','Dawki','Nohkalikai','Mawsynram','Nongriat','Laitlum'],
    'Mizoram':           ['Aizawl','Phawngpui','Champhai','Reiek','Tam Dil'],
    'Nagaland':          ['Kohima','Hornbill Festival','Dzukou Valley','Dimapur','Mokokchung','Khonoma'],
    'Odisha':            ['Puri','Bhubaneswar','Konark','Chilika Lake','Simlipal','Bhitarkanika','Daringbadi','Gopalpur','Cuttack','Rayagada'],
    'Punjab':            ['Amritsar','Ludhiana','Patiala','Anandpur Sahib','Wagah Border','Fatehgarh Sahib','Bathinda'],
    'Rajasthan':         ['Jaipur','Udaipur','Jodhpur','Jaisalmer','Pushkar','Ranthambore','Mount Abu','Bikaner','Ajmer','Bundi','Chittorgarh','Kumbhalgarh','Bharatpur','Mandawa','Sawai Madhopur','Shekhawati','Alwar','Tonk'],
    'Sikkim':            ['Gangtok','Pelling','Lachung','Yumthang Valley','Goechala','Ravangla','Namchi','Zuluk','Yuksom','Dzongri'],
    'Tamil Nadu':        ['Chennai','Ooty','Kodaikanal','Madurai','Mahabalipuram','Rameswaram','Thanjavur','Kanyakumari','Yercaud','Pondicherry','Coimbatore','Salem','Chettinad','Mudumalai','Valparai','Courtallam','Vellore'],
    'Telangana':         ['Hyderabad','Warangal','Nagarjunasagar','Ramappa','Medak','Bhongir','Karimnagar','Nizamabad'],
    'Tripura':           ['Agartala','Neermahal','Sepahijala','Unakoti','Jampui Hills'],
    'Uttar Pradesh':     ['Agra','Varanasi','Lucknow','Mathura','Vrindavan','Ayodhya','Prayagraj','Sarnath','Dudhwa','Chitrakoot','Fatehpur Sikri'],
    'Uttarakhand':       ['Rishikesh','Haridwar','Mussoorie','Nainital','Jim Corbett','Auli','Chopta','Lansdowne','Kedarnath','Badrinath','Valley of Flowers','Roopkund','Chakrata','Munsiyari','Ranikhet','Binsar','Chaukori'],
    'West Bengal':       ['Kolkata','Darjeeling','Kalimpong','Sundarbans','Bishnupur','Dooars','Siliguri','Lava','Lolegaon','Sandakphu'],
    'Andaman Islands':   ['Port Blair','Havelock Island','Neil Island','Baratang','Ross Island','Diglipur','Long Island'],
    'Lakshadweep':       ['Agatti','Bangaram','Kavaratti','Minicoy'],
    'Delhi':             ['Old Delhi','New Delhi','Chandni Chowk','Qutub Minar','Lodhi Garden','Hauz Khas'],
    'Jammu & Kashmir':   ['Srinagar','Gulmarg','Pahalgam','Sonamarg','Patnitop','Vaishno Devi','Doodhpathri'],
}


def get_destination_context(destination: str) -> dict:
    """Fetch basic context about destination from free APIs."""
    context = {'destination': destination}

    # 1. Wikipedia summary
    try:
        url  = f'https://en.wikipedia.org/api/rest_v1/page/summary/{destination.replace(" ", "_")}'
        resp = requests.get(url, timeout=8, headers={'User-Agent': 'PackVote/1.0'})
        if resp.status_code == 200:
            data = resp.json()
            context['description'] = data.get('extract', '')[:500]
            context['wiki_url']    = data.get('content_urls', {}).get('desktop', {}).get('page', '')
    except Exception as e:
        print(f'  Wikipedia error: {e}')
    
    if not context.get('description'):
        context['description'] = f'{destination} is a popular travel destination in India.'

    # 2. Weather from wttr.in
    try:
        resp = requests.get(
            f'https://wttr.in/{destination}?format=j1',
            timeout=8, headers={'User-Agent': 'PackVote/1.0'}
        )
        if resp.status_code == 200:
            data    = resp.json()
            current = data['current_condition'][0]
            context['weather'] = {
                'temp_c':      current['temp_C'],
                'description': current['weatherDesc'][0]['value'],
                'humidity':    current['humidity'],
            }
    except Exception as e:
        print(f'  Weather error: {e}')
        context['weather'] = {'temp_c': 'N/A', 'description': 'Data unavailable'}

    return context


def research_destination_with_groq(destination: str, context: dict) -> dict:
    """
    Use Groq AI to research destination and extract:
    - Top 15-20 real attractions with names
    - Top 5-8 must-try foods with restaurant names
    - Local events/festivals
    - Transportation info
    - Best areas to stay
    
    Returns structured data for itinerary generation.
    """
    if not GROQ_API_KEY or not GROQ_API_KEY.strip():
        print('⚠️  GROQ_API_KEY not set, skipping research')
        return {}

    research_prompt = f"""You are a travel research expert. Research {destination}, India and provide factual, specific information.

DESTINATION: {destination}
WIKIPEDIA SUMMARY: {context.get('description', 'N/A')}
CURRENT WEATHER: {context.get('weather', {}).get('temp_c', 'N/A')}°C

Research and provide ONLY factual information about {destination}. Extract:

1. TOP ATTRACTIONS: List 15-20 REAL, NAMED tourist attractions, landmarks, temples, forts, museums, viewpoints, lakes, markets, etc. Use EXACT NAMES (e.g., "Hawa Mahal", "City Palace", not "palace in city center").

2. MUST-TRY FOOD: List 5-8 famous local dishes with REAL restaurant/place names where tourists can find them.

3. LOCAL EVENTS: List 2-4 festivals, fairs, or annual events specific to {destination}.

4. HOW TO REACH: Nearest airport, railway station, and bus terminals with distances.

5. WHERE TO STAY: Recommend 2-3 popular areas/neighborhoods for accommodation.

6. LOCAL TRANSPORT: Main modes of local transport used by tourists.

Respond ONLY in this exact JSON format (no markdown, no extra text):
{{
  "destination": "{destination}",
  "attractions": [
    "Real Attraction Name 1",
    "Real Attraction Name 2",
    ...15-20 items
  ],
  "must_try_food": [
    {{"dish": "Dish Name", "where": "Restaurant/Area Name", "type": "veg/nonveg/both"}},
    ...5-8 items
  ],
  "local_events": [
    "Event/Festival Name 1",
    "Event/Festival Name 2"
  ],
  "how_to_reach": {{
    "nearest_airport": "Airport Name (Distance km)",
    "nearest_railway": "Railway Station Name",
    "bus_terminals": "Bus stand/ISBT name"
  }},
  "stay_areas": ["Area 1", "Area 2", "Area 3"],
  "local_transport": "Main transport modes",
  "best_time_to_visit": "Month range"
}}"""

    try:
        print(f'🔍 Researching {destination} with Groq AI...')
        
        resp = requests.post(
            GROQ_URL,
            headers={
                'Authorization': f'Bearer {GROQ_API_KEY}',
                'Content-Type':  'application/json'
            },
            json={
                'model':'llama-3.3-70b-versatile',
                'max_tokens':  3000,
                'temperature': 0.3,  # Lower temp for factual research
                'messages': [
                    {
                        'role':    'system',
                        'content': 'You are a travel research expert. Provide only factual, verified information about destinations. Always respond with valid JSON only, no markdown.'
                    },
                    {'role': 'user', 'content': research_prompt}
                ]
            },
            timeout=45
        )

        if resp.status_code != 200:
            print(f'❌ Groq research API error: HTTP {resp.status_code}')
            return {}

        response_json = resp.json()
        if 'choices' not in response_json or not response_json['choices']:
            print('❌ Invalid Groq research response')
            return {}

        raw = response_json['choices'][0]['message']['content'].strip()
        
        # Strip markdown fences
        if raw.startswith('```'):
            lines = raw.split('\n')
            raw   = '\n'.join(lines[1:-1] if lines[-1].strip() == '```' else lines[1:])
        
        research_data = json.loads(raw)
        print(f'✅ Research completed: {len(research_data.get("attractions", []))} attractions found')
        return research_data

    except Exception as e:
        print(f'❌ Groq research failed: {type(e).__name__}: {str(e)}')
        return {}


def generate_ai_itinerary(
    destination:   str,
    duration:      int   = 5,
    budget:        str   = 'medium',
    travel_styles: list  = None,
    month:         str   = 'December',
    group_size:    int   = 4,
    food_pref:     str   = 'both',
    group_type:    str   = 'friends'
) -> dict:
    """
    Generate full AI itinerary using two-step Groq approach:
    1. Research destination to get real attractions/food
    2. Generate detailed itinerary using researched data
    
    Falls back to minimal rule-based only when Groq fails.
    """
    if travel_styles is None:
        travel_styles = ['culture']

    # Step 1: Get basic context
    print(f'📍 Getting context for {destination}...')
    context = get_destination_context(destination)

    # Step 2: Research destination with Groq
    research_data = research_destination_with_groq(destination, context)
    
    # If research failed and no Groq key, use minimal fallback
    if not research_data and not GROQ_API_KEY:
        print('⚠️  No Groq key available, using minimal fallback')
        return _minimal_fallback(destination, duration, budget, context)

    # Step 3: Generate itinerary with researched data
    if not GROQ_API_KEY or not GROQ_API_KEY.strip():
        print('⚠️  GROQ_API_KEY not set for itinerary generation')
        return _minimal_fallback(destination, duration, budget, context)

    # Extract researched data
    attractions = research_data.get('attractions', [])
    must_try_food = research_data.get('must_try_food', [])
    local_events = research_data.get('local_events', [])
    
    if not attractions:
        print('⚠️  No attractions found in research, using fallback')
        return _minimal_fallback(destination, duration, budget, context)

    attr_text = ', '.join(attractions[:15])
    food_text = ', '.join([f"{f['dish']} at {f['where']}" for f in must_try_food[:6]])
    event_text = ', '.join(local_events[:3]) if local_events else 'Check local tourism board'
    
    budget_daily = {
        'low': '₹1500', 
        'medium': '₹4000', 
        'high': '₹9000', 
        'luxury': '₹20000'
    }.get(budget, '₹4000')

    itinerary_prompt = f"""You are an expert Indian travel planner. Create a detailed {duration}-day itinerary for {destination}.

GROUP DETAILS:
- Size: {group_size} {group_type}
- Budget: {budget} ({budget_daily}/person/day)
- Travel Month: {month}
- Preferences: {', '.join(travel_styles)}
- Food: {food_pref}

DESTINATION INFO:
{context.get('description', '')[:300]}

VERIFIED ATTRACTIONS (use ONLY these real names):
{attr_text}

MUST-TRY FOOD:
{food_text}

LOCAL EVENTS: {event_text}
WEATHER: {context.get('weather', {}).get('temp_c', 'N/A')}°C - {context.get('weather', {}).get('description', '')}

HOW TO REACH:
{json.dumps(research_data.get('how_to_reach', {}), indent=2)}

STAY AREAS: {', '.join(research_data.get('stay_areas', ['city center']))}
LOCAL TRANSPORT: {research_data.get('local_transport', 'Auto rickshaw / taxi')}

CRITICAL RULES:
1. Use ONLY the real attraction names listed above - NO generic placeholders
2. Distribute attractions across {duration} days - different spots each day
3. Use ONLY the real food items listed above
4. Every activity must reference a REAL named place
5. Provide realistic costs based on {budget} budget
6. Include practical tips and transport details
7. Food recommendations must match {food_pref} preference

Generate a practical {duration}-day itinerary. Respond ONLY in this exact JSON (no markdown):
{{
  "destination": "{destination}",
  "duration": {duration},
  "theme": "catchy one-line trip theme",
  "highlights": ["Real attraction 1", "Real attraction 2", "Real attraction 3"],
  "reach": {{
    "by_train": "nearest station + popular trains",
    "by_bus": "bus routes",
    "by_flight": "nearest airport + airlines",
    "by_road": "distance from major city + route"
  }},
  "stay": {{
    "budget": "specific hotel/hostel name + price",
    "mid": "specific hotel name + price",
    "luxury": "specific hotel name + price"
  }},
  "days": [
    {{
      "day": 1,
      "title": "Day theme",
      "morning": {{
        "time": "7:00 AM - 10:30 AM",
        "activity": "REAL attraction name from list",
        "description": "detailed 2-3 sentence description",
        "cost": "₹XX per person",
        "transport": "how to reach",
        "tips": "specific insider tip"
      }},
      "afternoon": {{
        "time": "11:30 AM - 3:30 PM",
        "activity": "REAL attraction name from list",
        "description": "detailed 2-3 sentence description",
        "cost": "₹XX per person",
        "transport": "how to reach",
        "tips": "specific insider tip"
      }},
      "evening": {{
        "time": "5:00 PM - 8:30 PM",
        "activity": "REAL attraction name from list",
        "description": "detailed 2-3 sentence description",
        "cost": "₹XX per person",
        "transport": "how to reach",
        "tips": "specific insider tip"
      }},
      "lunch": {{
        "restaurant": "specific name from food list",
        "area": "locality",
        "cuisine": "cuisine type",
        "type": "veg/nonveg/both",
        "must_try": "dish name from food list",
        "price_for_two": "₹XXX"
      }},
      "dinner": {{
        "restaurant": "specific name from food list",
        "area": "locality",
        "cuisine": "cuisine type",
        "type": "veg/nonveg/both",
        "must_try": "dish name from food list",
        "price_for_two": "₹XXX"
      }},
      "day_cost_per_person": "₹XXXX",
      "local_transport": "main transport today",
      "pro_tip": "specific actionable tip"
    }}
  ],
  "must_eat": [
    {{"dish": "dish name", "where": "place name", "price": "₹XX", "type": "veg/nonveg"}}
  ],
  "packing": ["item 1", "item 2", "item 3", "item 4", "item 5"],
  "safety_tips": ["tip 1", "tip 2", "tip 3"],
  "useful_apps": ["app - purpose"],
  "total_cost": {{
    "per_person_inr": "₹XXXXX",
    "for_group_inr": "₹XXXXX",
    "breakdown": {{
      "accommodation": "₹XXXX",
      "food": "₹XXXX",
      "transport": "₹XXXX",
      "activities": "₹XXXX",
      "miscellaneous": "₹XXXX"
    }}
  }}
}}"""

    try:
        print(f'📝 Generating itinerary with Groq AI...')
        
        resp = requests.post(
            GROQ_URL,
            headers={
                'Authorization': f'Bearer {GROQ_API_KEY}',
                'Content-Type':  'application/json'
            },
            json={
                'model':       'llama-3.3-70b-versatile',
                'max_tokens':  4096,
                'temperature': 0.7,
                'messages': [
                    {
                        'role':    'system',
                        'content': (
                            'You are an expert Indian travel planner. '
                            'Always respond with valid JSON only, no markdown. '
                            'Use ONLY real, verified attraction and restaurant names provided. '
                            'Never invent generic placeholders.'
                        )
                    },
                    {'role': 'user', 'content': itinerary_prompt}
                ]
            },
            timeout=60
        )

        if resp.status_code != 200:
            print(f'❌ Groq itinerary API error: HTTP {resp.status_code}')
            raise Exception(f'HTTP {resp.status_code}')

        response_json = resp.json()
        if 'choices' not in response_json or not response_json['choices']:
            raise ValueError('Invalid response structure')

        raw = response_json['choices'][0]['message']['content'].strip()
        
        # Strip markdown fences
        if raw.startswith('```'):
            lines = raw.split('\n')
            raw   = '\n'.join(lines[1:-1] if lines[-1].strip() == '```' else lines[1:])

        itinerary = json.loads(raw)
        itinerary['ai_powered']  = True
        itinerary['ai_model']    = 'LLaMA 3 70B via Groq (two-step research + generation)'
        itinerary['context']     = context
        itinerary['research_data'] = research_data
        
        print(f'✅ Complete itinerary generated for {destination}')
        return itinerary

    except Exception as e:
        print(f'❌ Groq itinerary generation failed: {type(e).__name__}: {str(e)}')
        print('📝 Falling back to minimal itinerary...')
        return _minimal_fallback(destination, duration, budget, context, research_data)


def _minimal_fallback(
    destination: str, 
    duration: int, 
    budget: str, 
    context: dict,
    research_data: dict = None
) -> dict:
    """
    Minimal fallback when Groq is unavailable.
    Uses research_data if available from successful research step.
    """
    daily_costs = {'low': 1500, 'medium': 4000, 'high': 9000, 'luxury': 20000}
    daily = daily_costs.get(budget, 4000)
    
    # Try to use researched attractions if available
    attractions = []
    if research_data and research_data.get('attractions'):
        attractions = research_data['attractions'][:15]
    
    # Fallback generic activities
    if not attractions:
        attractions = [
            f'{destination} Main Market',
            f'{destination} Heritage Walk',
            f'{destination} City Temple/Fort',
            f'{destination} Local Museum',
            f'{destination} Viewpoint',
            f'{destination} Cultural Center',
            f'{destination} Traditional Bazaar',
            f'{destination} Nature Spot',
        ]
    
    # Build minimal days
    days = []
    for d in range(1, duration + 1):
        idx = (d - 1) * 3
        days.append({
            'day': d,
            'title': f'Day {d} - Explore {destination}',
            'morning': {
                'time': '8:00 AM - 11:00 AM',
                'activity': attractions[idx % len(attractions)],
                'description': f'Visit and explore this popular attraction. Great for morning visits.',
                'cost': f'₹{int(daily * 0.15)}',
                'transport': 'Local taxi / auto rickshaw',
                'tips': 'Arrive early to avoid crowds'
            },
            'afternoon': {
                'time': '12:00 PM - 4:00 PM',
                'activity': attractions[(idx + 1) % len(attractions)],
                'description': f'Spend your afternoon exploring this must-see location.',
                'cost': f'₹{int(daily * 0.20)}',
                'transport': 'Walking / local transport',
                'tips': 'Carry water and sun protection'
            },
            'evening': {
                'time': '5:00 PM - 8:00 PM',
                'activity': attractions[(idx + 2) % len(attractions)],
                'description': f'End your day at this beautiful evening spot.',
                'cost': f'₹{int(daily * 0.10)}',
                'transport': 'Auto rickshaw',
                'tips': 'Best for sunset views'
            },
            'lunch': {
                'restaurant': f'Local restaurant near {attractions[(idx + 1) % len(attractions)]}',
                'area': 'City center',
                'cuisine': 'Local Indian',
                'type': 'both',
                'must_try': 'Regional thali',
                'price_for_two': f'₹{int(daily * 0.12)}'
            },
            'dinner': {
                'restaurant': 'Traditional local eatery',
                'area': 'Main market',
                'cuisine': 'Regional specialties',
                'type': 'both',
                'must_try': 'Local delicacy',
                'price_for_two': f'₹{int(daily * 0.15)}'
            },
            'day_cost_per_person': f'₹{daily}',
            'local_transport': 'Auto rickshaw / taxi',
            'pro_tip': f'Ask locals for hidden gems on Day {d}'
        })

    return {
        'destination': destination,
        'duration': duration,
        'theme': f'{duration}-Day {destination} Discovery',
        'highlights': attractions[:3],
        'reach': {
            'by_train': f'Check IRCTC for trains to nearest station',
            'by_bus': f'State transport buses available',
            'by_flight': f'Search flights on travel portals',
            'by_road': f'Well connected by road'
        },
        'stay': {
            'budget': f'Budget hostels/guesthouses - ₹800-1500/night',
            'mid': f'Mid-range hotels - ₹2500-4000/night',
            'luxury': f'Premium hotels/resorts - ₹8000+/night'
        },
        'days': days,
        'must_eat': research_data.get('must_try_food', [
            {'dish': 'Local thali', 'where': 'City restaurants', 'price': '₹150', 'type': 'both'},
            {'dish': 'Regional specialty', 'where': 'Market area', 'price': '₹200', 'type': 'both'}
        ]) if research_data else [
            {'dish': 'Local thali', 'where': 'City restaurants', 'price': '₹150', 'type': 'both'}
        ],
        'packing': [
            'Comfortable walking shoes',
            'Light cotton clothes',
            'Sunscreen and hat',
            'Power bank',
            'Cash for local shops'
        ],
        'safety_tips': [
            'Keep emergency numbers handy',
            'Use registered taxis only',
            'Keep photocopies of ID'
        ],
        'useful_apps': [
            'Google Maps - navigation',
            'Zomato - food discovery',
            'Uber/Ola - transportation'
        ],
        'total_cost': {
            'per_person_inr': f'₹{daily * duration + 5000}',
            'for_group_inr': f'₹{(daily * duration + 5000) * 4}',
            'breakdown': {
                'accommodation': f'₹{int(daily * 0.35 * duration)}',
                'food': f'₹{int(daily * 0.30 * duration)}',
                'transport': f'₹{int(daily * 0.20 * duration)}',
                'activities': f'₹{int(daily * 0.15 * duration)}',
                'miscellaneous': f'₹{3000}'
            }
        },
        'ai_powered': False,
        'ai_model': 'Minimal rule-based fallback',
        'context': context,
        'note': 'This is a basic itinerary. For best results, please set GROQ_API_KEY environment variable.'
    }


# ── Example Usage ──────────────────────────────────────────────────────────

if __name__ == '__main__':
    # Test with a destination
    result = generate_ai_itinerary(
        destination='Udaipur',
        duration=4,
        budget='medium',
        travel_styles=['culture', 'heritage'],
        month='January',
        group_size=2,
        food_pref='both',
        group_type='couple'
    )
    
    print('\n' + '='*80)
    print('GENERATED ITINERARY')
    print('='*80)
    print(json.dumps(result, indent=2, ensure_ascii=False))