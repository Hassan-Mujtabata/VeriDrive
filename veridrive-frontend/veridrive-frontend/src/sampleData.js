// Sample report used for demo mode (no backend required)
// This matches the exact JSON structure the FastAPI backend will return.
// When the backend is ready, this file is no longer needed.

export const SAMPLE_REPORT = {
  request_id: "demo-001",
  status: "complete",
  listing: {
    make: "Toyota",
    model: "Corolla",
    year: 2019,
    mileage_km: 95000,
    asking_price_aed: 28000,
    description:
      "First owner, no accidents, full service history at Toyota dealer. GCC spec, well maintained. Single owner since new. Clean interior and exterior.",
    seller_name: "Ahmed Al Mansouri",
    seller_phone: "+971 50 123 4567",
    emirate: "Dubai",
    listing_url: "https://dubai.dubizzle.com/motors/used-cars/toyota/corolla/",
    photos: [
      "https://images.unsplash.com/photo-1621007947382-bb3c3994e3fb?w=800&q=80",
      "https://images.unsplash.com/photo-1502877338535-766e1452684a?w=800&q=80",
      "https://images.unsplash.com/photo-1494976388531-d1058494cdd8?w=800&q=80"
    ]
  },
  trust_score: {
    composite_score: 62,
    seller_credibility_subscore: 55,
    price_fairness_subscore: 88,
    vin_history_subscore: 45,
    recommendation:
      "This vehicle shows mixed indicators. The asking price is fair relative to the current market, but there are significant discrepancies between the seller's claims and the VIN report. The seller stated no accidents, however records show one incident in 2021. We recommend requesting official service records and an independent inspection before proceeding."
  },
  price_analysis: {
    comparable_count: 23,
    median_market_price: 31500,
    asking_price_aed: 28000,
    price_difference_percent: -11.1,
    fairness_score: 88,
    recommended_min_aed: 25000,
    recommended_max_aed: 28500
  },
  vin_report: {
    available: true,
    vin: "JTDBL40E499012345",
    data_source: "VehicleDatabases",
    accident_count: 1,
    ownership_count: 2,
    title_status: "Clean",
    theft_record: false,
    sources: {
      nhtsa: {
        Make: "Toyota",
        Model: "Corolla",
        ModelYear: "2019",
        BodyClass: "Sedan/Saloon",
        PlantCountry: "JAPAN",
        FuelTypePrimary: "Gasoline"
      },
      vehicle_databases: {
        make: "Toyota",
        model: "Corolla",
        year: "2019",
        trim: "LE",
        body_type: "Sedan/Saloon",
        doors: "4"
      },
      title_check: {
        salvage: false
      }
    }
  },
  red_flags: [
    {
      severity: "high",
      title: "Accident History Discrepancy",
      description:
        "Seller claimed no accidents during the verification call. VIN report (Vehicle Databases Title Check) shows 1 recorded accident in 2021.",
      source_module: "VIN"
    },
    {
      severity: "high",
      title: "Ownership Count Mismatch",
      description:
        "Listing states first owner. VIN database records show 2 previous registered owners.",
      source_module: "VIN"
    },
    {
      severity: "medium",
      title: "Seller Hesitation on Service Records",
      description:
        "Seller paused for an extended period when asked about service history documentation. Could not provide immediate verification.",
      source_module: "Voice"
    },
    {
      severity: "low",
      title: "Below-Market Pricing",
      description:
        "Asking price is 11% below the market median for equivalent vehicles. While potentially a good deal, unusually low prices can sometimes indicate undisclosed issues.",
      source_module: "Price"
    }
  ],
  voice_call: {
    available: true,
    seller_credibility_score: 55,
    call_outcome: "completed",
    duration_seconds: 187,
    transcript_summary:
      "Seller was cooperative initially but hesitated when asked about accident history. Claimed to be the first and only owner with no accidents. Confirmed GCC spec and dealer service history but could not provide documentation immediately. Tone shifted noticeably when pressed on the number of previous owners."
  }
}
