//------------------------------------------------------------------------------
// <copyright file="Timer.h" company="Microsoft">
// 	 
//	 Copyright 2013 Microsoft Corporation 
// 	 
//	Licensed under the Apache License, Version 2.0 (the "License"); 
//	you may not use this file except in compliance with the License.
//	You may obtain a copy of the License at
// 	 
//		 http://www.apache.org/licenses/LICENSE-2.0 
// 	 
//	Unless required by applicable law or agreed to in writing, software 
//	distributed under the License is distributed on an "AS IS" BASIS,
//	WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. 
//	See the License for the specific language governing permissions and 
//	limitations under the License. 
// 	 
// </copyright>
//------------------------------------------------------------------------------

#pragma once

#include <Windows.h>

namespace Timing
{
    /// <summary>
    /// Timer is a minimal class to get the system time in seconds
    /// </summary>
    class Timer
    {
    private:
        /// <summary>
        ///  Whether the timer is initialized and can be used.
        /// </summary>
        bool initialized;

        /// <summary>
        ///  The clock frequency in ticks per second.
        /// </summary>
        LARGE_INTEGER frequency;

    public:
        /// <summary>
        ///  Initializes a new instance of the <see cref="Timer"/> class.
        /// </summary>
        Timer();

        /// <summary>
        ///  Gets the absolute time.
        /// </summary>
        /// <returns>Returns the absolute time in s.</returns>
        double AbsoluteTime();
    };
};
