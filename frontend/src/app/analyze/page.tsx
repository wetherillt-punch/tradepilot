import { prisma } from '@/lib/prisma'

export const dynamic = 'force-dynamic'

async function getCases() {
  const cases = await prisma.case.findMany({
    select: {
      id: true,
      caseNumber: true,
      patientAge: true,
      patientSex: true,
      admitDate: true,
      records: true,
      createdAt: true,
    },
    orderBy: {
      caseNumber: 'asc'
    }
  })
  return cases
}

export default async function Home() {
  const cases = await getCases()

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Sepsis Audit Cases</h1>
          <p className="mt-2 text-gray-600">Review and analyze potential sepsis cases</p>
        </div>

        {cases.length === 0 ? (
          <div className="bg-white rounded-lg shadow p-8 text-center">
            <p className="text-gray-500">No cases found.</p>
          </div>
        ) : (
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {cases.map((caseItem) => {
              const records = typeof caseItem.records === 'string' 
                ? JSON.parse(caseItem.records) 
                : caseItem.records

              return (
                <a
                  key={caseItem.id}
                  href={`/cases/${caseItem.id}`}
                  className="block bg-white rounded-lg shadow hover:shadow-md transition-shadow p-6"
                >
                  <div className="flex items-start justify-between mb-4">
                    <div>
                      <h3 className="text-lg font-semibold text-gray-900">
                        {caseItem.caseNumber}
                      </h3>
                      <p className="text-sm text-gray-500">
                        {caseItem.patientAge}y {caseItem.patientSex}
                      </p>
                    </div>
                    <span className="px-3 py-1 text-xs font-medium rounded-full bg-blue-100 text-blue-800">
                      Pending
                    </span>
                  </div>
                  
                  <div className="space-y-2 text-sm text-gray-600">
                    <div className="flex justify-between">
                      <span>Admit:</span>
                      <span className="font-medium">
                        {new Date(caseItem.admitDate).toLocaleDateString()}
                      </span>
                    </div>
                  </div>

                  <div className="mt-4 pt-4 border-t border-gray-200">
                    <span className="text-sm text-blue-600 font-medium">
                      View Details →
                    </span>
                  </div>
                </a>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
